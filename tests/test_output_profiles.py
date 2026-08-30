from __future__ import annotations

from pathlib import Path

import dublocal.output_profiles as profiles


def _probe(*, height=1080, codec="h264", pix_fmt="yuv420p", bitrate=8_000_000):
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": codec,
                "pix_fmt": pix_fmt,
                "height": height,
                "bit_rate": str(bitrate),
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"bit_rate": str(bitrate + 192_000)},
    }


def test_auto_profiles_are_format_specific(monkeypatch, tmp_path: Path):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr(profiles, "config_path", lambda: path)

    assert profiles.resolved_profile("mkv") == "original"
    assert profiles.resolved_profile("mp4") == "balanced"
    assert profiles.resolved_profile("share") == "compact"
    assert profiles.acquisition_quality("mkv", "source") == "source"
    assert profiles.acquisition_quality("mp4", "source") == "1080"
    assert profiles.acquisition_quality("share", "source") == "720"


def test_shareable_auto_is_compact_and_predictable(monkeypatch, tmp_path: Path):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr(profiles, "config_path", lambda: path)

    plan_480 = profiles.output_plan("share", _probe(height=480, bitrate=2_500_000), "source")
    assert plan_480.resolved_profile == "compact"
    assert plan_480.target_height == 480
    assert plan_480.encode_video is True
    assert plan_480.video_bitrate == "500k"
    assert plan_480.audio_bitrate == "96k"

    mb_per_minute = profiles.approximate_mb_per_minute("share", 480)
    assert mb_per_minute is not None
    assert 4.0 < mb_per_minute < 5.0


def test_shareable_auto_caps_large_sources_at_720(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(profiles, "config_path", lambda: tmp_path / "profiles.json")
    plan = profiles.output_plan("share", _probe(height=2160, bitrate=24_000_000), "source")
    assert plan.target_height == 720
    assert plan.encode_video is True
    assert plan.video_bitrate == "900k"


def test_mkv_auto_preserves_video_but_explicit_limit_still_downscales(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(profiles, "config_path", lambda: tmp_path / "profiles.json")

    original = profiles.output_plan("mkv", _probe(height=1080, bitrate=12_000_000), "source")
    assert original.resolved_profile == "original"
    assert original.encode_video is False

    limited = profiles.output_plan("mkv", _probe(height=1080, bitrate=12_000_000), "480")
    assert limited.encode_video is True
    assert limited.target_height == 480
    assert limited.video_bitrate == "1200k"


def test_mp4_auto_reencodes_oversized_or_incompatible_video(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(profiles, "config_path", lambda: tmp_path / "profiles.json")

    oversized = profiles.output_plan("mp4", _probe(height=1080, bitrate=9_000_000), "source")
    assert oversized.resolved_profile == "balanced"
    assert oversized.encode_video is True
    assert oversized.video_bitrate == "2600k"

    incompatible = profiles.output_plan(
        "mp4",
        _probe(height=720, codec="vp9", pix_fmt="yuv420p", bitrate=900_000),
        "source",
    )
    assert incompatible.encode_video is True
    assert incompatible.reason == "H.264 compatibility"


def test_saved_profile_overrides_auto(monkeypatch, tmp_path: Path):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr(profiles, "config_path", lambda: path)
    profiles.save_profiles("compact", "high", "balanced")

    assert profiles.resolved_profile("mkv") == "compact"
    assert profiles.resolved_profile("mp4") == "high"
    assert profiles.resolved_profile("share") == "balanced"
    assert profiles.acquisition_quality("mkv", "source") == "720"
    assert profiles.acquisition_quality("share", "source") == "1080"
