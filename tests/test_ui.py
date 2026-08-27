from __future__ import annotations

import dublocal
from dublocal.ui import (
    MATRIX_CSS,
    _settings_version_html,
    _source_card_status,
    _suggest_voice_controls,
    _translation_preview_rows,
    _translation_result_note,
    _translation_route_languages,
    _voice_dropdown,
    build_app,
)


def test_translation_model_routes():
    assert _translation_route_languages("en-to-many") == ("en", "hu")
    assert _translation_route_languages("many-to-en") == ("hu", "en")
    assert _translation_route_languages("both") == ("hu", "de")


def test_translation_preview_puts_target_text_before_source():
    rows = [["00:00:01,000", "00:00:02,000", "Hello", "Привет"]]
    assert _translation_preview_rows(rows) == [
        ["00:00:01,000", "00:00:02,000", "Привет", "Hello"]
    ]
    assert _translation_result_note(rows) == "[translation] 1/1 segment(s) differ from the source"


def test_voice_dropdown_uses_language_default():
    update = _voice_dropdown("en-GB")
    assert update.value == "bf_emma"
    assert any(value == "bm_george" for _label, value in update.choices)


def test_unsupported_translated_language_clears_kokoro_voice():
    language_update, voice_update = _suggest_voice_controls(
        "Translated subtitles",
        "en",
        "hu",
    )
    assert language_update.value is None
    assert voice_update.value is None


def test_source_english_suggests_american_kokoro():
    language_update, voice_update = _suggest_voice_controls(
        "Source subtitles",
        "en",
        "hu",
    )
    assert language_update.value == "en-US"
    assert voice_update.value == "af_heart"


def test_source_card_status_is_persistent_and_human_readable():
    assert "not loaded" in _source_card_status({}).lower()
    loaded = _source_card_status(
        {
            "kind": "youtube",
            "title": "Example video",
            "duration": 125,
            "subtitle_tracks": [{"value": "en"}, {"value": "ru"}],
        }
    )
    assert "Loaded · OK" in loaded
    assert "Example video" in loaded
    assert "2:05" in loaded
    assert "2 caption tracks" in loaded


def test_settings_version_is_visible_and_uses_running_package_version():
    html = _settings_version_html()
    assert "Running local development build" in html
    assert f"v{dublocal.__version__}" in html


def test_primary_framework_accent_is_overridden_to_dublocal_green():
    assert "--primary-500: #42ef83" in MATRIX_CSS
    assert "button[role=\"tab\"][aria-selected=\"true\"]" in MATRIX_CSS
    assert "accent-color: #42ef83" in MATRIX_CSS
    assert ".dl-stage-status" in MATRIX_CSS


def test_tabbed_ui_builds():
    demo = build_app()
    assert demo is not None
