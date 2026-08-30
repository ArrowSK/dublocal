from __future__ import annotations

from pathlib import Path

import dublocal.magic_flow as magic
import dublocal.output_profile_runtime as runtime
import dublocal.output_profiles as profiles
import dublocal.shareable_burn as share_burn


def _probe(*, height=480, bitrate=2_500_000):
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "height": height,
                "width": round(height * 16 / 9),
                "bit_rate": str(bitrate),
            },
            {"codec_type": "audio", "codec_name": "aac", "channels": 2},
        ],
        "format": {"duration": "60.0", "bit_rate": str(bitrate + 192_000)},
    }


def _job_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_shareable_export_uses_compact_auto_rates(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(profiles, "config_path", lambda: tmp_path / "profiles.json")
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source")
    seen: dict[str, list[str]] = {}

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe())
    monkeypatch.setattr(magic, "_require", lambda _name: "ffmpeg")
    monkeypatch.setattr(magic, "_new_job_dir", lambda _prefix: _job_dir(tmp_path, "share"))

    def fake_run(command, **_kwargs):
        seen["command"] = list(command)
        Path(command[-1]).write_bytes(b"mp4")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)

    output = runtime._make_shareable_media_profiled(
        source,
        {"kind": "local", "title": "Clip", "path": str(source)},
        "en",
        video_quality="source",
    )

    command = seen["command"]
    assert command[command.index("-b:v") + 1] == "500k"
    assert command[command.index("-b:a") + 1] == "96k"
    assert "h264_videotoolbox" in command
    assert output.is_file()


def test_burned_shareable_export_uses_same_compact_profile(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(profiles, "config_path", lambda: tmp_path / "profiles.json")
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source")
    subtitle = tmp_path / "clip.en.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello.\n", encoding="utf-8")
    seen: dict[str, list[str]] = {}

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe())
    monkeypatch.setattr(magic, "_new_job_dir", lambda _prefix: _job_dir(tmp_path, "burn"))
    monkeypatch.setattr(share_burn, "_burn_ffmpeg", lambda: "ffmpeg-full")

    def fake_run(command, **_kwargs):
        seen["command"] = list(command)
        Path(command[-1]).write_bytes(b"mp4")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)
    burn = runtime._burned_shareable_media_profiled(share_burn)

    output = burn(
        source,
        {"kind": "local", "title": "Clip", "path": str(source)},
        "en",
        subtitle_path=subtitle,
        video_quality="source",
    )

    command = seen["command"]
    assert command[0] == "ffmpeg-full"
    assert command[command.index("-b:v") + 1] == "500k"
    assert command[command.index("-b:a") + 1] == "96k"
    assert "subtitles=filename=" in command[command.index("-vf") + 1]
    assert output.is_file()
