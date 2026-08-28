from __future__ import annotations

import dublocal.ui_v060 as ui


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


def test_main_has_simple_and_advanced_subtabs():
    demo = ui.build_app()
    strings = _config_strings(demo.config)

    assert "Main" in strings
    assert "Simple" in strings
    assert "Advanced" in strings
    assert "Settings" in strings
    assert "Run Magic Flow" in strings
    assert "Load source" in strings


def test_simple_copy_does_not_put_detailed_workflow_below_magic_flow():
    demo = ui.build_app()
    strings = "\n".join(_config_strings(demo.config))

    assert "Most users only need this tab." in strings
    assert "keeps the detailed workflow below" not in strings
    assert "Advanced workflow" in strings
