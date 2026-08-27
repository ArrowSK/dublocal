from pathlib import Path

from dublocal.timeline import parse_srt
from dublocal.voice_text import prepare_voice_srt, spoken_text


def test_spoken_text_removes_bracketed_cues_without_changing_real_dialogue():
    assert spoken_text("[MUSIC]") == ""
    assert spoken_text("[LAUGHS] Hello [APPLAUSE]") == "Hello"
    assert spoken_text("This [quietly] still speaks.") == "This still speaks."


def test_prepare_voice_srt_keeps_timing_but_drops_tag_only_rows(tmp_path: Path):
    source = tmp_path / "movie.en.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n[MUSIC]\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\n[LAUGHS] Hello there.\n",
        encoding="utf-8",
    )
    output = prepare_voice_srt(source)
    segments = parse_srt(output.read_text(encoding="utf-8"))
    assert len(segments) == 1
    assert segments[0].index == 2
    assert segments[0].start_ms == 2000
    assert segments[0].text == "Hello there."
