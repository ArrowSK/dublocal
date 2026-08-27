from __future__ import annotations

from dublocal.stage_status import subtitles_ready_status, translation_ready_status, voice_ready_status


def test_stage_statuses_are_clear_on_success_and_failure(tmp_path):
    subtitle = tmp_path / "source.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    translated = tmp_path / "translated.srt"
    translated.write_text("1\n00:00:00,000 --> 00:00:01,000\nПривет\n", encoding="utf-8")
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"RIFF")

    assert subtitles_ready_status(
        str(subtitle), [["0", "1", "Hello"]], "en", method="Transcribed"
    ) == "✓ **Transcribed · OK** · 1 timed segment · English"
    assert translation_ready_status(
        str(translated), [["0", "1", "Привет", "Hello"]], "en", "ru"
    ) == "✓ **Translated · OK** · 1 segment · English → Russian"
    assert "Voice generated · OK" in voice_ready_status(
        str(voice), [["0", "1", "1", "OK", "Привет"]], "ru", "af_heart"
    )
    assert "Translation failed" in translation_ready_status(None, [], "en", "ru")
