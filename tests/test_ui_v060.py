from __future__ import annotations

import dublocal.ui_v060 as ui


def test_contextual_auto_is_forwarded_when_no_cached_language(monkeypatch):
    seen = {}
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_LANGUAGE", "auto")
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_INFO", {})

    def fake_translate(mode, subtitle_path, source_language, target_language, progress):
        seen["source"] = source_language
        return None, [], "ok", "", "card"

    monkeypatch.setattr(ui.detailed, "_ORIGINAL_TRANSLATE", fake_translate)

    result = ui._translate_with_state_auto_safe(
        "contextual",
        "/tmp/captions.srt",
        "auto",
        "es",
        None,
    )

    assert seen["source"] == "auto"
    assert result[2] == "ok"


def test_cached_transcription_language_is_consumed_by_translate(monkeypatch):
    seen = {}
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_LANGUAGE", "English")
    monkeypatch.setattr(ui.detailed, "_LAST_SOURCE_INFO", {})

    def fake_translate(mode, subtitle_path, source_language, target_language, progress):
        seen["source"] = source_language
        return None, [], "ok", "", "card"

    monkeypatch.setattr(ui.detailed, "_ORIGINAL_TRANSLATE", fake_translate)

    ui._translate_with_state_auto_safe(
        "contextual",
        "/tmp/captions.srt",
        "auto",
        "es",
        None,
    )

    assert seen["source"] == "en"


def test_magic_ui_builds():
    demo = ui.build_app()
    assert demo is not None
