from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dublocal.cancellation_ui as cancellation_ui
import dublocal.magic_flow as magic


def _probe_payload(*, video_codec: str = "vp9", pix_fmt: str = "yuv420p", height: int = 1080):
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": video_codec,
                "pix_fmt": pix_fmt,
                "height": height,
                "width": 1920,
            },
            {"codec_type": "audio", "codec_name": "opus", "channels": 2},
        ],
        "format": {"duration": "60.0"},
    }


def test_magic_audio_preferences_preserve_original_track_and_request_single_voice():
    args = (
        "YouTube",
        "https://www.youtube.com/watch?v=test",
        None,
        True,
        "en",
        ["voice", "media"],
        "auto",
        "local-best",
        ["keep-original", "single-voice"],
        "share",
        "source",
    )

    updated, kwargs = cancellation_ui._apply_magic_audio_preferences(args, {})

    assert kwargs == {}
    assert updated[8] is True
    assert "single-voice" in updated[5]
    assert updated[9] == "share"


def test_single_voice_magic_flow_uses_best_overall_fallback_only(monkeypatch, tmp_path: Path):
    source_srt = tmp_path / "source.srt"
    source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello.\n", encoding="utf-8")
    voice_wav = tmp_path / "voice.wav"
    voice_wav.write_bytes(b"voice")
    seen: dict[str, object] = {}

    monkeypatch.setattr(magic, "inspect_magic_source", lambda *args, **kwargs: {"kind": "local", "title": "clip.mp4"})
    monkeypatch.setattr(
        magic,
        "recommend_subtitle_source",
        lambda *args, **kwargs: magic.SubtitleDecision("existing", "existing", track_value="track"),
    )
    monkeypatch.setattr(magic, "_prepare_source_subtitle", lambda *args, **kwargs: (source_srt, "en"))
    monkeypatch.setattr(magic, "export_subtitle", lambda path, _format: str(path))
    monkeypatch.setattr(magic, "suggested_kokoro_language", lambda _language: "en-US")
    monkeypatch.setattr(magic, "prepare_voice_srt", lambda path: Path(path))
    monkeypatch.setattr(
        magic,
        "resolve_auto_voice_plan",
        lambda *args, **kwargs: ("am_adam", {1: "af_heart", 2: "am_adam"}, "mixed vocal ranges"),
    )

    def fake_generate(*args, **kwargs):
        seen["segment_voices"] = kwargs.get("segment_voices")
        seen["voice"] = kwargs.get("voice")
        return SimpleNamespace(wav_path=voice_wav)

    monkeypatch.setattr(magic, "generate_voice_track_with_progress", fake_generate)

    result = magic.run_magic_flow(
        source_type="Local file",
        youtube_url="",
        local_file=str(tmp_path / "clip.mp4"),
        rights_confirmed=True,
        target_language="en",
        tasks=["voice", "single-voice"],
    )

    assert seen["voice"] == "am_adam"
    assert seen["segment_voices"] == {}
    assert result.voice_wav == voice_wav


def test_shareable_media_enforces_h264_aac_single_audio_and_faststart(monkeypatch, tmp_path: Path):
    source = tmp_path / "dubbed.mkv"
    source.write_bytes(b"source")
    subtitle = tmp_path / "clip.en.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello.\n", encoding="utf-8")
    seen: dict[str, object] = {}

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload())
    monkeypatch.setattr(magic, "_require", lambda name: name)

    def fake_run(command, **kwargs):
        seen["command"] = list(command)
        Path(command[-1]).write_bytes(b"mp4")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)

    output = magic._make_shareable_media(
        source,
        {"kind": "local", "title": "Clip", "path": str(source)},
        "en",
        subtitle_path=subtitle,
        subtitle_language="en",
        video_quality="source",
    )

    command = seen["command"]
    assert isinstance(command, list)
    assert "h264_videotoolbox" in command
    assert "yuv420p" in command
    assert "aac" in command
    assert "+faststart" in command
    maps = [command[index + 1] for index, item in enumerate(command[:-1]) if item == "-map"]
    assert maps == ["0:v:0", "0:a:0", "1:0"]
    assert output.suffix == ".mp4"
    assert ".share.en.mp4" in output.name


def test_production_ui_exposes_shareable_output_and_audio_voice_group():
    import dublocal.launcher_runtime as launcher_runtime

    app = launcher_runtime.build_app()
    rendered = str(app.get_config_file())

    assert "MP4 · Shareable · WhatsApp / Telegram · H.264 + AAC" in rendered
    assert "Audio & voice" in rendered
    assert "Single voice for the whole item · best overall match" in rendered
