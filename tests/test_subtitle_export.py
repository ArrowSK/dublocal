from __future__ import annotations

from pathlib import Path

from dublocal.subtitle_export import export_subtitle_timeline


_SAMPLE = """1
00:00:01,000 --> 00:00:02,500
Hello, world.

2
00:00:03,000 --> 00:00:04,000
Second line.
"""


def test_srt_export_reuses_normalized_timeline(tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(_SAMPLE, encoding="utf-8")
    assert export_subtitle_timeline(source, "srt") == source.resolve()


def test_vtt_txt_and_csv_exports(tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(_SAMPLE, encoding="utf-8")

    vtt = export_subtitle_timeline(source, "vtt")
    txt = export_subtitle_timeline(source, "txt")
    csv = export_subtitle_timeline(source, "csv")

    assert vtt.suffix == ".vtt"
    assert "WEBVTT" in vtt.read_text(encoding="utf-8")
    assert "00:00:01.000 --> 00:00:02.500" in vtt.read_text(encoding="utf-8")

    assert txt.read_text(encoding="utf-8") == "Hello, world.\nSecond line.\n"

    csv_text = csv.read_text(encoding="utf-8")
    assert "start,end,text" in csv_text
    assert '"Hello, world."' in csv_text
