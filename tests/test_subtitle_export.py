from __future__ import annotations

from pathlib import Path

from dublocal.subtitle_export import export_subtitle


SRT = """1
00:00:01,000 --> 00:00:02,500
Hello

2
00:00:03,000 --> 00:00:04,000
[MUSIC]
"""


def test_srt_export_reuses_internal_timeline(tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(SRT, encoding="utf-8")
    assert export_subtitle(source, "srt") == source.resolve()


def test_vtt_export_preserves_timing_and_tags(tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(SRT, encoding="utf-8")
    output = export_subtitle(source, "vtt")
    text = output.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT\n")
    assert "00:00:01.000 --> 00:00:02.500" in text
    assert "[MUSIC]" in text


def test_txt_export_is_plain_text(tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(SRT, encoding="utf-8")
    output = export_subtitle(source, "txt")
    assert output.read_text(encoding="utf-8") == "Hello\n[MUSIC]\n"
