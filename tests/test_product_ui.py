from __future__ import annotations

from pathlib import Path

from dublocal import product_ui as ui
from dublocal import tts
from dublocal.tts_provider_refinement import _apply_provider_metadata


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


def test_product_ui_builds_with_current_simple_advanced_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        ui,
        "model_setup_state",
        lambda: type("State", (), {"first_run_pending": False})(),
    )
    snapshot = (
        dict(tts.KOKORO_LANGUAGES),
        list(tts.KOKORO_LANGUAGE_CHOICES),
        dict(tts._PREPARE_TEXT),
        dict(tts._TRANSLATION_TO_KOKORO),
    )
    try:
        _apply_provider_metadata()
        demo = ui.build_app()
        strings = _config_strings(demo.config)
        assert "Main" in strings
        assert "Simple" in strings
        assert "Advanced" in strings
        assert "Settings" in strings
        assert "Model Setup" in strings
        assert "Model Manager" in strings
        assert "Run Magic Flow" in strings
        assert "Update DubLocal" in strings
        assert "Local TTS providers · Russian & custom models" in strings
        assert "Vocal separation · music-aware dubbing" in strings
    finally:
        languages, choices, prepare_text, translation_map = snapshot
        tts.KOKORO_LANGUAGES.clear()
        tts.KOKORO_LANGUAGES.update(languages)
        tts.KOKORO_LANGUAGE_CHOICES[:] = choices
        tts._PREPARE_TEXT.clear()
        tts._PREPARE_TEXT.update(prepare_text)
        tts._TRANSLATION_TO_KOKORO.clear()
        tts._TRANSLATION_TO_KOKORO.update(translation_map)


def test_contextual_auto_is_forwarded_when_no_cached_language(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_LANGUAGE", "auto")
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_INFO", {})

    def fake_translate(mode, subtitle_path, source_language, target_language, progress):
        seen["source"] = source_language
        return None, [], "ok", "", "card"

    monkeypatch.setattr(ui.detailed, "_ORIGINAL_TRANSLATE", fake_translate)
    result = ui._translate_with_state_auto_safe(
        "contextual", "/tmp/captions.srt", "auto", "es", None
    )
    assert seen["source"] == "auto"
    assert result[2] == "ok"


def test_cached_transcription_language_is_consumed_by_translate(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_LANGUAGE", "English")
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_INFO", {})

    def fake_translate(mode, subtitle_path, source_language, target_language, progress):
        seen["source"] = source_language
        return None, [], "ok", "", "card"

    monkeypatch.setattr(ui.detailed, "_ORIGINAL_TRANSLATE", fake_translate)
    ui._translate_with_state_auto_safe("contextual", "/tmp/captions.srt", "auto", "es", None)
    assert seen["source"] == "en"


def test_force_local_quality_defaults_to_best_when_accurate_is_installed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    accurate = tmp_path / "accurate.bin"
    accurate.write_bytes(b"model")
    monkeypatch.setattr(ui, "whisper_model_path", lambda _model_id: accurate)
    assert ui._default_local_transcription_policy() == "local-best"


def test_force_local_quality_defaults_to_fast_when_accurate_is_not_installed(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
