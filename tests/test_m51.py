from __future__ import annotations

from pathlib import Path

import dublocal.m51 as m51


def _probe_payload(*, audio_count: int = 1, subtitle_count: int = 0, height: int = 2160):
    streams = [{"codec_type": "video", "codec_name": "h264", "height": height, "width": 3840}]
    streams.extend({"codec_type": "audio", "codec_name": "aac"} for _ in range(audio_count))
    streams.extend({"codec_type": "subtitle", "codec_name": "subrip"} for _ in range(subtitle_count))
    return {"streams": streams, "format": {"duration": "60.0"}}


def _write_srt(path: Path, text: str = "Hello") -> None:
    path.write_text(f"1\n00:00:01,000 --> 00:00:03,000\n{text}\n", encoding="utf-8")


def test_strong_mix_uses_timed_dialogue_guide(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    voice = tmp_path / "voice.wav"
    srt = tmp_path / "source.srt"
    source.write_bytes(b"src")
    voice.write_bytes(b"voice")
    _write_srt(srt)
    seen = {}

    monkeypatch.setattr(m51.m5, "_require", lambda name: name)
    monkeypatch.setattr(m51.m5, "_probe", lambda _path: _probe_payload())

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"mix")

    monkeypatch.setattr(m51.m5, "_run_ffmpeg_progress", fake_run)
    output = m51.create_dubbed_mix(
        source,
        voice,
        tmp_path,
        dialogue_subtitle_path=srt,
    )
    graph = seen["command"][seen["command"].index("-filter_complex") + 1]
    assert "aevalsrc" in graph
    assert "sidechaincompress=threshold=0.08:ratio=12" in graph
    assert "between(t\\,0.880\\,3.350)" in graph
    assert output.is_file()


def test_mkv_embeds_source_and_translation_subtitles(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    mixed = tmp_path / "mix.m4a"
    original = tmp_path / "Movie.en.srt"
    translated = tmp_path / "Movie.es.srt"
    source.write_bytes(b"src")
    mixed.write_bytes(b"mix")
    _write_srt(original, "Hello")
    _write_srt(translated, "Hola")
    seen = {}

    monkeypatch.setattr(m51.m5, "_require", lambda name: name)
    monkeypatch.setattr(m51.m5, "_probe", lambda _path: _probe_payload(subtitle_count=1, height=1080))

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"output")

    monkeypatch.setattr(m51.m5, "_run_ffmpeg_progress", fake_run)
    result = m51.remux_dubbed_media(
        source,
        mixed,
        {"kind": "local", "title": "Movie.mkv", "path": str(source)},
        "es",
        mode="replace",
        container="mkv",
        output_dir=tmp_path,
        video_quality="source",
        source_subtitle_path=original,
        translated_subtitle_path=translated,
        source_language="en",
        translated_language="es",
    )
    command = seen["command"]
    maps = [command[i + 1] for i, item in enumerate(command[:-1]) if item == "-map"]
    assert "0:s?" in maps
    assert "2:0" in maps
    assert "3:0" in maps
    assert "title=Original subtitles · eng" in command
    assert "title=DubLocal translation · spa" in command
    assert result.embedded_subtitle_tracks == 2
    assert result.video_stream_copy is True


def test_local_lower_quality_explicitly_uses_videotoolbox(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    mixed = tmp_path / "mix.m4a"
    source.write_bytes(b"src")
    mixed.write_bytes(b"mix")
    seen = {}

    monkeypatch.setattr(m51.m5, "_require", lambda name: name)
    monkeypatch.setattr(m51.m5, "_probe", lambda _path: _probe_payload(height=2160))

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"output")

    monkeypatch.setattr(m51.m5, "_run_ffmpeg_progress", fake_run)
    result = m51.remux_dubbed_media(
        source,
        mixed,
        {"kind": "local", "title": "Movie.mkv", "path": str(source)},
        "es",
        mode="replace",
        container="mkv",
        output_dir=tmp_path,
        video_quality="1080",
        source_subtitle_path=None,
        translated_subtitle_path=None,
        source_language="en",
        translated_language="es",
    )
    command = seen["command"]
    assert "h264_videotoolbox" in command
    assert "scale=-2:1080" in command
    assert result.video_stream_copy is False


def test_youtube_quality_selector_caps_height_without_local_transcode():
    assert "height<=1080" in m51._youtube_format("1080")
    assert m51._youtube_format("source") == "bestvideo*+bestaudio/best"
