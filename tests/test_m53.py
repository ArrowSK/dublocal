from __future__ import annotations

from pathlib import Path

import dublocal.m53 as m53


def _probe_payload(*, audio_count: int = 1, subtitle_count: int = 0, height: int = 1080):
    streams = [{"codec_type": "video", "codec_name": "h264", "height": height, "width": 1920}]
    streams.extend({"codec_type": "audio", "codec_name": "aac"} for _ in range(audio_count))
    streams.extend({"codec_type": "subtitle", "codec_name": "subrip"} for _ in range(subtitle_count))
    return {"streams": streams, "format": {"duration": "60.0"}}


def _write_srt(path: Path, text: str = "Hello") -> None:
    path.write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{text}\n", encoding="utf-8")


def test_balanced_mix_keeps_original_bed_below_full_scale(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    voice = tmp_path / "voice.wav"
    srt = tmp_path / "source.srt"
    source.write_bytes(b"src")
    voice.write_bytes(b"voice")
    _write_srt(srt)
    seen = {}

    monkeypatch.setattr(m53.m5, "_require", lambda name: name)
    monkeypatch.setattr(m53.m5, "_probe", lambda _path: _probe_payload())

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"mix")

    monkeypatch.setattr(m53.m5, "_run_ffmpeg_progress", fake_run)
    output = m53.create_balanced_dubbed_mix(
        source,
        voice,
        tmp_path,
        dialogue_subtitle_path=srt,
    )

    graph = seen["command"][seen["command"].index("-filter_complex") + 1]
    assert "volume=0.620" in graph
    assert "sidechaincompress=threshold=0.045:ratio=18" in graph
    assert "acompressor=threshold=0.35:ratio=2" in graph
    assert "alimiter=limit=0.90" in graph
    assert output.is_file()


def test_subtitle_only_package_keeps_original_audio_and_adds_no_dub(monkeypatch, tmp_path: Path):
    source = tmp_path / "movie.mkv"
    subtitle = tmp_path / "Movie.en.srt"
    source.write_bytes(b"src")
    _write_srt(subtitle)
    seen = {}

    monkeypatch.setattr(
        m53.m51,
        "acquire_source_media",
        lambda info, output_dir, video_quality, progress_callback=None: source,
    )
    monkeypatch.setattr(m53.m5, "_probe", lambda _path: _probe_payload(audio_count=2, subtitle_count=1))
    monkeypatch.setattr(m53.m5, "_require", lambda name: name)

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"package")

    monkeypatch.setattr(m53.m5, "_run_ffmpeg_progress", fake_run)
    result = m53.package_subtitled_media(
        {"kind": "local", "title": "Movie.mkv", "path": str(source)},
        subtitle,
        "en",
        container="mkv",
        video_quality="source",
    )

    command = seen["command"]
    maps = [command[i + 1] for i, item in enumerate(command[:-1]) if item == "-map"]
    assert "0:a?" in maps
    assert "0:s?" in maps
    assert "1:0" in maps
    assert "title=DubLocal source subtitles · eng" in command
    assert result.video_stream_copy is True
    assert ".subtitles.en.mkv" in result.output_path.name


def test_install_runtime_refinements_leaves_timing_to_native_kokoro_generation():
    old_fit = m53.m5.fit_voice_timing
    old_mix = m53.m51.create_dubbed_mix
    try:
        m53.install_runtime_refinements()
        assert m53.m5.fit_voice_timing is old_fit
        assert m53.m51.create_dubbed_mix is m53.create_balanced_dubbed_mix
    finally:
        m53.m5.fit_voice_timing = old_fit
        m53.m51.create_dubbed_mix = old_mix
