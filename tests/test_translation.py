from __future__ import annotations

from pathlib import Path

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
