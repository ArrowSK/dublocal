from __future__ import annotations

import dublocal
from dublocal.hungarian_tts import install_hungarian_metadata
from dublocal.subtitle_export import SUBTITLE_FORMAT_CHOICES
from dublocal.ui import (
    MATRIX_CSS,
    _caption_quality_note,
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


def test_translated_hungarian_offers_local_voice():
    install_hungarian_metadata()
    language_update, voice_update = _suggest_voice_controls(
        "Translated subtitles",
        "en",
        "hu",
    )
    assert language_update.value == "hu"
    assert voice_update.value is not None
    assert any(value == voice_update.value for _label, value in voice_update.choices)


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


def test_automatic_caption_note_warns_about_source_recognition_quality():
    info = {
        "kind": "youtube",
        "subtitle_tracks": [
            {"value": "yt:auto:en", "source": "auto"},
            {"value": "yt:manual:en", "source": "manual"},
        ],
    }
    auto = _caption_quality_note(info, "yt:auto:en")
    manual = _caption_quality_note(info, "yt:manual:en")
    assert "Automatic YouTube captions" in auto
    assert "cannot be repaired reliably by translation" in auto
    assert "Large v3 Turbo" in auto
    assert "Creator/embedded" in manual


def test_subtitle_download_formats_default_to_srt_and_offer_vtt_txt():
    values = [value for _label, value in SUBTITLE_FORMAT_CHOICES]
    assert values == ["srt", "vtt", "txt"]


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
