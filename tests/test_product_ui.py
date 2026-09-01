from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from dublocal import production_ui as ui


def _config_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_config_strings(item))
        return result
    if isinstance(value, (list, tuple)):
        result: list[str] = []
        for item in value:
            result.extend(_config_strings(item))
        return result
    return []


def test_product_ui_builds_with_current_standard_advanced_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        ui,
        "model_setup_state",
        lambda: type("State", (), {"first_run_pending": False})(),
    )
    demo = ui.build_app()
    strings = _config_strings(demo.config)
    assert "Main" in strings
    assert "Standard" in strings
    assert "Advanced" in strings
    assert "Settings" in strings
    assert "Model Setup" in strings
    assert "Model Manager" in strings
    assert "Start Processing" in strings
    assert "Update DubLocal" in strings
    assert "Local TTS providers · Russian & custom models" in strings
    assert "Vocal separation · music-aware dubbing" in strings
    assert "Output Profiles" in strings
    assert "Storage & Cleanup" in strings


def test_contextual_auto_is_forwarded_without_global_cached_language(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "captions.srt"
    source.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello.\n", encoding="utf-8")
    output = tmp_path / "translated.srt"
    output.write_text("1\n00:00:00,000 --> 00:00:01,000\nHola.\n", encoding="utf-8")
    seen: dict[str, str] = {}

    def fake_translate(path, source_language, target_language, *, progress_callback=None):
        seen["source"] = source_language
        seen["target"] = target_language
        return SimpleNamespace(srt_path=output, segments=[], route="fake")

    monkeypatch.setattr(ui, "translate_srt_contextual_with_progress", fake_translate)
    result = ui._advanced_translate("contextual", str(source), "auto", "es", {}, None)
    assert seen == {"source": "auto", "target": "es"}
    assert result[3]


def test_force_local_quality_defaults_to_best_when_accurate_is_installed(monkeypatch, tmp_path: Path) -> None:
    accurate = tmp_path / "accurate.bin"
    accurate.write_bytes(b"model")
    monkeypatch.setattr(ui, "whisper_model_path", lambda _model_id: accurate)
    assert ui._default_local_transcription_policy() == "local-best"


def test_force_local_quality_defaults_to_fast_when_accurate_is_not_installed(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.bin"
    monkeypatch.setattr(ui, "whisper_model_path", lambda _model_id: missing)
    assert ui._default_local_transcription_policy() == "local-fast"


def test_product_theme_keeps_loader_green_and_alignment_rules() -> None:
    css = ui.MATRIX_CSS
    assert "--loader-color: var(--dl-green)" in css
    assert '[data-testid="status-tracker"] .progress-bar' in css
    assert ".dl-model-setup-card" in css
    assert ".dl-magic-shell > .form" in css
    assert ":has(.dl-magic-title)" in css
    assert ".dl-queue-note" in css
