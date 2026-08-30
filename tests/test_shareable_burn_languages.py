from __future__ import annotations

from pathlib import Path

import pytest

import dublocal.cancellation_ui as cancellation_ui
import dublocal.magic_flow as magic
import dublocal.shareable_burn as share_burn
from dublocal.language_extensions import install_language_extensions
from dublocal.media import DubLocalError


def _probe_payload():
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "height": 1080,
                "width": 1920,
            },
            {"codec_type": "audio", "codec_name": "aac", "channels": 2},
        ],
        "format": {"duration": "60.0"},
    }


def _burn_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "dubbed.mkv"
    source.write_bytes(b"source")
    subtitle = tmp_path / "clip.uk.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nПривіт.\n", encoding="utf-8")
    return source, subtitle


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


def test_burn_ffmpeg_prefers_normal_binary_when_it_has_subtitles(monkeypatch):
    monkeypatch.setattr(
        share_burn,
        "_subtitle_ffmpeg_candidates",
        lambda: ["/normal/ffmpeg", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"],
    )
    monkeypatch.setattr(
        share_burn,
        "_ffmpeg_has_filter",
        lambda executable, filter_name="subtitles": executable == "/normal/ffmpeg",
    )

    assert share_burn._burn_ffmpeg() == "/normal/ffmpeg"


def test_burn_ffmpeg_uses_keg_only_ffmpeg_full_when_normal_lacks_subtitles(monkeypatch):
    full = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
    monkeypatch.setattr(
        share_burn,
        "_subtitle_ffmpeg_candidates",
        lambda: ["/normal/ffmpeg", full],
    )
    monkeypatch.setattr(
        share_burn,
        "_ffmpeg_has_filter",
        lambda executable, filter_name="subtitles": executable == full,
    )

    assert share_burn._burn_ffmpeg() == full


def test_burn_ffmpeg_refuses_binary_without_subtitle_filter(monkeypatch):
    monkeypatch.setattr(share_burn, "_subtitle_ffmpeg_candidates", lambda: ["/normal/ffmpeg"])
    monkeypatch.setattr(share_burn, "_ffmpeg_has_filter", lambda *args, **kwargs: False)

    with pytest.raises(DubLocalError, match="subtitles/libass"):
        share_burn._burn_ffmpeg()


def test_burned_shareable_mp4_hardcodes_srt_and_keeps_one_audio(monkeypatch, tmp_path: Path):
    source, subtitle = _burn_fixture(tmp_path)
    seen: dict[str, object] = {}

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload())
    monkeypatch.setattr(share_burn, "_burn_ffmpeg", lambda: "ffmpeg")

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
    assert "yuv420p" in command
    assert "aac" in command
    assert "+faststart" in command
    assert "mov_text" not in command
    maps = [command[index + 1] for index, item in enumerate(command[:-1]) if item == "-map"]
    assert maps == ["0:v:0", "0:a:0"]
    assert ".share-burned.uk.mp4" in output.name


def test_real_encoder_failure_retries_same_subtitle_ffmpeg_with_libx264(monkeypatch, tmp_path: Path):
    source, subtitle = _burn_fixture(tmp_path)
    selected = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
    attempts: list[list[str]] = []

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload())
    monkeypatch.setattr(share_burn, "_burn_ffmpeg", lambda: selected)

    def fake_run(command, **kwargs):
        attempts.append(list(command))
        if len(attempts) == 1:
            raise DubLocalError("VideoToolbox encoder could not start")
        Path(command[-1]).write_bytes(b"mp4")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)

    output = share_burn._burned_shareable_media(
        source,
        {"kind": "local", "title": "Clip", "path": str(source)},
        "uk",
        subtitle_path=subtitle,
        video_quality="source",
    )

    assert output.is_file()
    assert len(attempts) == 2
    assert attempts[0][0] == selected
    assert attempts[1][0] == selected
    assert "h264_videotoolbox" in attempts[0]
    assert "libx264" in attempts[1]


def test_missing_filter_does_not_waste_time_on_h264_fallback(monkeypatch, tmp_path: Path):
    source, subtitle = _burn_fixture(tmp_path)
    attempts: list[list[str]] = []

    monkeypatch.setattr(magic, "_probe", lambda _path: _probe_payload())
    monkeypatch.setattr(share_burn, "_burn_ffmpeg", lambda: "ffmpeg")

    def fake_run(command, **kwargs):
        attempts.append(list(command))
        raise DubLocalError("Error opening output files: Filter not found")

    monkeypatch.setattr(magic, "_run_ffmpeg_progress", fake_run)

    with pytest.raises(DubLocalError, match="subtitles/libass"):
        share_burn._burned_shareable_media(
            source,
            {"kind": "local", "title": "Clip", "path": str(source)},
            "uk",
            subtitle_path=subtitle,
            video_quality="source",
        )

    assert len(attempts) == 1
    assert "h264_videotoolbox" in attempts[0]


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
