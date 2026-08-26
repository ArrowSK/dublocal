from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import huggingface_hub

import dublocal.translation as translation
from dublocal.translation import TranslatedSegment


def test_translation_language_normalisation_and_routes():
    assert translation.normalise_language_code("eng") == "en"
    assert translation.normalise_language_code("en-US") == "en"
    assert translation.normalise_language_code("hun") == "hu"
    assert translation.normalise_language_code("deu") == "de"
    assert translation.normalise_language_code("und") == "auto"

    assert translation.required_model_ids("en", "hu") == ["en-to-many"]
    assert translation.required_model_ids("hu", "en") == ["many-to-en"]
    assert translation.required_model_ids("hu", "de") == ["many-to-en", "en-to-many"]


def test_translation_models_live_outside_repository(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(translation, "user_data_dir", lambda app: str(tmp_path / "app-data"))

    path = translation.translation_model_path("en-to-many")

    assert path == tmp_path / "app-data" / "models" / "translation" / "en-to-many"


def test_translation_model_reuses_shared_hf_snapshot_and_remove_keeps_snapshot(
    monkeypatch, tmp_path: Path
):
    app_data = tmp_path / "app-data"
    snapshot = tmp_path / "hf-cache" / "snapshot"
    snapshot.mkdir(parents=True)
    for name in translation._MODEL_FILES:
        (snapshot / name).write_bytes(b"model-file")

    metadata = translation.TRANSLATION_MODELS["en-to-many"]
    monkeypatch.setattr(translation, "user_data_dir", lambda app: str(app_data))
    monkeypatch.setattr(translation, "translation_engine_ready", lambda: True)
    monkeypatch.setattr(translation, "_sha256", lambda path: metadata["weight_sha256"])
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda **kwargs: str(snapshot))

    registered = translation.install_translation_model("en-to-many")

    assert registered.is_symlink()
    assert registered.resolve() == snapshot.resolve()
    assert translation._model_valid("en-to-many") is True
    assert translation._model_storage("en-to-many") == "shared HF cache"

    removed = translation.remove_translation_models()

    assert removed == 1
    assert not registered.exists()
    assert snapshot.exists()
    assert (snapshot / "model.safetensors").exists()


def test_translation_can_use_external_compatible_runtime(monkeypatch, tmp_path: Path):
    current = tmp_path / "dublocal-python"
    external = tmp_path / "studio-python"
    current.write_text("", encoding="utf-8")
    external.write_text("", encoding="utf-8")
    runtime = SimpleNamespace(python=external, label="narroam-studio")
    captured = {}

    monkeypatch.setattr(translation.sys, "executable", str(current))
    monkeypatch.setattr(translation, "_translation_runtime", lambda: runtime)

    def fake_external(active_runtime, model_id, texts, target_tag, batch_size):
        captured.update(
            runtime=active_runtime,
            model_id=model_id,
            texts=texts,
            target_tag=target_tag,
            batch_size=batch_size,
        )
        return ["Szia"]

    monkeypatch.setattr(translation, "_translate_external", fake_external)

    result = translation._translate_with_model(
        "en-to-many",
        ["Hello"],
        target_language="hu",
    )

    assert result == ["Szia"]
    assert captured["runtime"] is runtime
    assert captured["model_id"] == "en-to-many"
    assert captured["target_tag"] == "hun"


def test_translate_srt_preserves_timings(monkeypatch, tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:01,250 --> 00:00:03,900\nHello world.\n\n"
        "2\n00:00:05,000 --> 00:00:06,125\nNext line.\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "translation-job"
    output_dir.mkdir()

    monkeypatch.setattr(translation, "_new_job_dir", lambda prefix: output_dir)

    def fake_translate_segments(segments, source_language, target_language):
        source_segments = list(segments)
        assert source_language == "en"
        assert target_language == "hu"
        return [
            TranslatedSegment(
                index=item.index,
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                source_text=item.text,
                translated_text=f"HU: {item.text}",
            )
            for item in source_segments
        ]

    monkeypatch.setattr(translation, "translate_segments", fake_translate_segments)

    result = translation.translate_srt(source, "en", "hu")

    assert result.srt_path.name == "captions.hu.srt"
    assert result.route == "English → Hungarian"
    text = result.srt_path.read_text(encoding="utf-8")
    assert "00:00:01,250 --> 00:00:03,900" in text
    assert "00:00:05,000 --> 00:00:06,125" in text
    assert "HU: Hello world." in text
    assert "HU: Next line." in text
