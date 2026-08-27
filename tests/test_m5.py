from __future__ import annotations

from pathlib import Path

import dublocal.m5 as m5


def _probe_payload(audio_count: int = 2, video_count: int = 1):
    streams = []
    streams.extend({"codec_type": "video", "codec_name": "h264"} for _ in range(video_count))
    streams.extend({"codec_type": "audio", "codec_name": "aac"} for _ in range(audio_count))
    return {"streams": streams, "format": {"duration": "60.0"}}


def test_replace_mode_stream_copies_video_and_replaces_only_primary_audio(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    mixed = tmp_path / "dubbed-mix.m4a"
    source.write_bytes(b"src")
    mixed.write_bytes(b"mix")
    seen = {}

    monkeypatch.setattr(m5, "_probe", lambda _path: _probe_payload(audio_count=2))
    monkeypatch.setattr(m5, "_require", lambda name: name)

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"output")

    monkeypatch.setattr(m5, "_run_ffmpeg_progress", fake_run)
    result = m5.remux_dubbed_media(
        source,
        mixed,
        {"kind": "local", "title": "Movie.mkv", "path": str(source)},
        "es",
        mode="replace",
        container="mkv",
        output_dir=tmp_path,
    )

    command = seen["command"]
    assert ["-c:v", "copy"] == command[command.index("-c:v") : command.index("-c:v") + 2]
    assert "1:a:0" in command
    assert "0:a:1?" in command
    assert "0:a:0" not in [command[i + 1] for i, item in enumerate(command[:-1]) if item == "-map"]
    assert result.output_audio_tracks == 2
    assert result.video_stream_copy is True


def test_add_mode_keeps_original_audio_and_adds_dublocal_track(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    mixed = tmp_path / "dubbed-mix.m4a"
    source.write_bytes(b"src")
    mixed.write_bytes(b"mix")
    seen = {}

    monkeypatch.setattr(m5, "_probe", lambda _path: _probe_payload(audio_count=2))
    monkeypatch.setattr(m5, "_require", lambda name: name)

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"output")

    monkeypatch.setattr(m5, "_run_ffmpeg_progress", fake_run)
    result = m5.remux_dubbed_media(
        source,
        mixed,
        {"kind": "local", "title": "Movie.mkv", "path": str(source)},
        "es",
        mode="add",
        container="mkv",
        output_dir=tmp_path,
    )

    maps = [seen["command"][i + 1] for i, item in enumerate(seen["command"][:-1]) if item == "-map"]
    assert "0:a?" in maps
    assert "1:a:0" in maps
    assert result.output_audio_tracks == 3
    assert result.output_path.name == "Movie.dub.es.mkv"


def test_mp4_stream_copy_failure_recommends_mkv(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.webm"
    mixed = tmp_path / "dubbed-mix.m4a"
    source.write_bytes(b"src")
    mixed.write_bytes(b"mix")
    monkeypatch.setattr(m5, "_probe", lambda _path: _probe_payload(audio_count=1))
    monkeypatch.setattr(m5, "_require", lambda name: name)

    def fail(*args, **kwargs):
        raise m5.DubLocalError("codec not supported in mp4")

    monkeypatch.setattr(m5, "_run_ffmpeg_progress", fail)
    try:
        m5.remux_dubbed_media(
            source,
            mixed,
            {"kind": "local", "title": "Movie.webm", "path": str(source)},
            "es",
            mode="replace",
            container="mp4",
            output_dir=tmp_path,
        )
    except m5.DubLocalError as exc:
        assert "Choose MKV" in str(exc)
        assert "does not silently re-encode video" in str(exc)
    else:
        raise AssertionError("expected MP4 compatibility failure")
