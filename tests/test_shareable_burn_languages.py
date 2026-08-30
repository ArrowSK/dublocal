from __future__ import annotations

from pathlib import Path

import pytest

import dublocal.cancellation_ui as cancellation_ui
import dublocal.magic_flow as magic
import dublocal.shareable_burn as share_burn
from dublocal.language_extensions import install_language_extensions
from dublocal.media import DubLocalError


def _probe_payload(height: int = 1080):
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "height": height,
                "width": int(height * 16 / 9),
            },
            {"codec_type": "audio", "codec_name": "aac", "channels": 2},
        ],
        "format": {"duration": "60.0"},
    }


def test_magic_preferences_request_shareable_subtitle_burn():
    args = (
        "YouTube",
        "https://www.youtube.com/watch?v=test",
        None,
        True,
        "uk",
        ["translate", "media"],
        "auto",
        "local-best",
        ["keep-original", "burn-share-subs"],
        "share",
        "source",
    )

    updated, kwargs = cancellation_ui._apply_magic_audio_preferences(args, {})

    assert kwargs == {}
    assert "burn-share-subs" in updated[5]
    assert updated[8] is True
    assert updated[9] == "share"


def test_burned_shareable_mp4_hardcodes_srt_and_keeps_one_audio(monkeypatch, tmp_path: Path):
    source = tmp_path / "dubbed.mkv"
    source.write_bytes(b"source")
    subtitle = tmp_path / "clip.uk.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nПривіт.\n", encoding="utf-8")
    seen: dict[str, object] = {}

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload())
    monkeypatch.setattr(magic, "_require", lambda name: name)
    monkeypatch.setattr(share_burn, "_subtitle_capable_ffmpeg", lambda ffmpeg: ffmpeg)

    def fake_run(command, **kwargs):
        seen["command"] = list(command)
        Path(command[-1]).write_bytes(b"mp4")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)

    output = share_burn._burned_shareable_media(
        source,
        {"kind": "local", "title": "Clip", "path": str(source)},
        "uk",
        subtitle_path=subtitle,
        video_quality="source",
    )

    command = seen["command"]
    assert isinstance(command, list)
    assert "-vf" in command
    filter_graph = command[command.index("-vf") + 1]
    assert "subtitles=filename=" in filter_graph
    assert "h264_videotoolbox" in command
    assert "3000k" in command
    assert "yuv420p" in command
    assert "aac" in command
    assert "160k" in command
    assert "+faststart" in command
    assert "mov_text" not in command
    maps = [command[index + 1] for index, item in enumerate(command[:-1]) if item == "-map"]
    assert maps == ["0:v:0", "0:a:0"]
    assert ".share-burned.uk.mp4" in output.name


def test_normal_shareable_mp4_is_reencoded_for_predictable_size(monkeypatch, tmp_path: Path):
    source = tmp_path / "already-h264.mp4"
    source.write_bytes(b"source")
    seen: dict[str, object] = {}

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload())
    monkeypatch.setattr(magic, "_require", lambda name: name)

    def fake_run(command, **kwargs):
        seen["command"] = list(command)
        Path(command[-1]).write_bytes(b"mp4")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)

    output = share_burn._make_shareable_with_optional_burn(
        source,
        {"kind": "local", "title": "Clip", "path": str(source)},
        "en",
        video_quality="source",
    )

    command = seen["command"]
    assert isinstance(command, list)
    assert "h264_videotoolbox" in command
    assert "copy" not in command
    assert "3000k" in command
    assert "160k" in command
    assert output.name.endswith(".share.en.mp4")


def test_shareable_source_preset_caps_4k_at_1080p(monkeypatch, tmp_path: Path):
    source = tmp_path / "4k.mp4"
    source.write_bytes(b"source")
    seen: dict[str, object] = {}

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload(2160))
    monkeypatch.setattr(magic, "_require", lambda name: name)

    def fake_run(command, **kwargs):
        seen["command"] = list(command)
        Path(command[-1]).write_bytes(b"mp4")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)

    share_burn._make_shareable_with_optional_burn(
        source,
        {"kind": "local", "title": "4K Clip", "path": str(source)},
        "en",
        video_quality="source",
    )

    command = seen["command"]
    assert isinstance(command, list)
    assert "-vf" in command
    assert command[command.index("-vf") + 1] == "scale=-2:1080"
    assert "3000k" in command


def test_burn_in_reports_missing_ffmpeg_subtitle_filter(monkeypatch, tmp_path: Path):
    source = tmp_path / "dubbed.mkv"
    source.write_bytes(b"source")
    subtitle = tmp_path / "clip.en.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello.\n", encoding="utf-8")

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload())
    monkeypatch.setattr(magic, "_require", lambda name: name)
    monkeypatch.setattr(share_burn, "_subtitle_capable_ffmpeg", lambda _ffmpeg: None)

    with pytest.raises(DubLocalError, match="subtitles.*filter"):
        share_burn._burned_shareable_media(
            source,
            {"kind": "local", "title": "Clip", "path": str(source)},
            "en",
            subtitle_path=subtitle,
            video_quality="source",
        )


def test_ukrainian_and_bulgarian_are_translation_choices_without_tts_claim():
    install_language_extensions()

    from dublocal import app, language_utils, translation
    from dublocal.tts import suggested_kokoro_language

    targets = dict((code, label) for label, code in app.TARGET_LANGUAGE_CHOICES)
    sources = dict((code, label) for label, code in app.LANGUAGE_CHOICES)
    assert targets["uk"] == "Ukrainian"
    assert targets["bg"] == "Bulgarian"
    assert sources["uk"] == "Ukrainian"
    assert sources["bg"] == "Bulgarian"
    assert translation.TRANSLATION_LANGUAGES["uk"]["label"] == "Ukrainian"
    assert translation.TRANSLATION_LANGUAGES["bg"]["label"] == "Bulgarian"
    assert language_utils.normalize_language_code("українська") == "uk"
    assert language_utils.normalize_language_code("български") == "bg"
    assert suggested_kokoro_language("uk") is None
    assert suggested_kokoro_language("bg") is None


def test_production_ui_exposes_burn_in_and_new_translation_languages():
    import dublocal.launcher_runtime as launcher_runtime

    app = launcher_runtime.build_app()
    rendered = str(app.get_config_file())

    assert "Burn subtitles into Shareable MP4" in rendered
    assert "Ukrainian" in rendered
    assert "Bulgarian" in rendered
