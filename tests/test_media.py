from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import dublocal.media as media


def test_inspect_local_media_classifies_subtitles(monkeypatch, tmp_path: Path):
    source = tmp_path / "episode.mkv"
    source.write_bytes(b"test")

    probe = {
        "format": {
            "duration": "90.5",
            "format_name": "matroska,webm",
            "format_long_name": "Matroska / WebM",
        },
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
            {"index": 1, "codec_type": "audio", "codec_name": "aac", "channels": 2, "tags": {"language": "eng"}},
            {"index": 2, "codec_type": "subtitle", "codec_name": "subrip", "tags": {"language": "eng", "title": "English"}},
            {"index": 3, "codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle", "tags": {"language": "deu"}},
        ],
    }

    monkeypatch.setattr(media, "_require_tool", lambda name: "/usr/bin/ffprobe")
    monkeypatch.setattr(media, "_run", lambda command: SimpleNamespace(stdout=json.dumps(probe)))

    info = media.inspect_local_media(source)

    assert info["title"] == "episode.mkv"
    assert info["duration"] == 90.5
    assert len(info["subtitle_tracks"]) == 2
    assert info["subtitle_tracks"][0]["text_capable"] is True
    assert info["subtitle_tracks"][1]["text_capable"] is False


def test_inspect_youtube_keeps_manual_and_auto_tracks(monkeypatch):
    class FakeYDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            assert download is False
            return {
                "id": "abc123",
                "title": "Example",
                "uploader": "Example channel",
                "duration": 42,
                "webpage_url": url,
                "subtitles": {"en": [{"ext": "vtt"}]},
                "automatic_captions": {"de": [{"ext": "vtt"}]},
            }

    monkeypatch.setattr(media, "YoutubeDL", FakeYDL)

    info = media.inspect_youtube("https://www.youtube.com/watch?v=abc123")

    values = {track["value"] for track in info["subtitle_tracks"]}
    assert values == {"yt:manual:en", "yt:auto:de"}


def test_extract_local_text_subtitle(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"media")
    output_dir = tmp_path / "job"
    output_dir.mkdir()

    info = {
        "kind": "local",
        "path": str(source),
        "subtitle_tracks": [
            {
                "value": "local:4",
                "index": 4,
                "codec": "subrip",
                "text_capable": True,
            }
        ],
    }

    monkeypatch.setattr(media, "_require_tool", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(media, "_new_job_dir", lambda prefix: output_dir)

    def fake_run(command):
        Path(command[-1]).write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(media, "_run", fake_run)

    result = media.extract_local_subtitle(info, "local:4")

    assert result.name == "captions.srt"
    assert "Hello" in result.read_text(encoding="utf-8")
