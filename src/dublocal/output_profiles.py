from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir


PROFILE_CHOICES = [
    ("Auto · format-aware", "auto"),
    ("Original · preserve source video", "original"),
    ("High · quality first", "high"),
    ("Balanced · good quality / smaller file", "balanced"),
    ("Compact · sharing / storage", "compact"),
]

FORMAT_LABELS = {
    "mkv": "MKV",
    "mp4": "MP4",
    "share": "Shareable MP4",
}

DEFAULT_PROFILES = {
    "mkv": "auto",
    "mp4": "auto",
    "share": "auto",
}

# Auto means something useful for the format rather than one global compromise.
# MKV is the preservation-oriented container; regular MP4 is a compatibility export;
# Shareable MP4 is intentionally compact and predictable.
_AUTO_PROFILE = {
    "mkv": "original",
    "mp4": "balanced",
    "share": "compact",
}

_PROFILE_MAX_HEIGHT = {
    "original": None,
    "high": 2160,
    "balanced": 1080,
    "compact": 720,
}

# H.264 targets are deliberately much lower than the old 2.5/5/10/16/25 Mbps
# ladder while remaining realistic for local hardware encoding. The compact 480p
# target is ~4.5 MB/min including audio, rather than implying an impossible 5 MB
# for a whole multi-minute video.
_VIDEO_KBPS = {
    "compact": {480: 500, 720: 900, 1080: 1500, 1440: 2400, 2160: 4200},
    "balanced": {480: 800, 720: 1400, 1080: 2600, 1440: 4200, 2160: 7200},
    "high": {480: 1200, 720: 2300, 1080: 4300, 1440: 7000, 2160: 12500},
}

_AUDIO_KBPS = {
    "compact": 96,
    "balanced": 128,
    "high": 160,
    "original": 192,
}

_STANDARD_HEIGHTS = (480, 720, 1080, 1440, 2160)
_VALID_PROFILES = {value for _label, value in PROFILE_CHOICES}


@dataclass(frozen=True, slots=True)
class OutputPlan:
    format_key: str
    requested_profile: str
    resolved_profile: str
    source_height: int | None
    target_height: int | None
    video_bitrate: str | None
    audio_bitrate: str
    encode_video: bool
    reason: str


def config_path() -> Path:
    root = Path(user_config_dir("DubLocal"))
    return root / "output-profiles.json"


def _normalise_format(format_key: str | None) -> str:
    value = str(format_key or "mkv").strip().lower()
    if value not in FORMAT_LABELS:
        return "mkv"
    return value


def _normalise_profile(value: str | None) -> str:
    selected = str(value or "auto").strip().lower()
    return selected if selected in _VALID_PROFILES else "auto"


def load_profiles() -> dict[str, str]:
    values = dict(DEFAULT_PROFILES)
    path = config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return values
    if not isinstance(raw, dict):
        return values
    for key in FORMAT_LABELS:
        if key in raw:
            values[key] = _normalise_profile(raw.get(key))
    return values


def save_profiles(mkv: str, mp4: str, share: str) -> dict[str, str]:
    values = {
        "mkv": _normalise_profile(mkv),
        "mp4": _normalise_profile(mp4),
        "share": _normalise_profile(share),
    }
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return values


def reset_profiles() -> dict[str, str]:
    return save_profiles(**DEFAULT_PROFILES)


def requested_profile(format_key: str) -> str:
    return load_profiles()[_normalise_format(format_key)]


def resolved_profile(format_key: str) -> str:
    key = _normalise_format(format_key)
    selected = requested_profile(key)
    return _AUTO_PROFILE[key] if selected == "auto" else selected


def _quality_height(video_quality: str | None) -> int | None:
    if not video_quality or str(video_quality).strip().lower() in {"source", "auto", "default"}:
        return None
    try:
        value = int(str(video_quality))
    except (TypeError, ValueError):
        return None
    return value if value in _STANDARD_HEIGHTS else None


def acquisition_quality(format_key: str, video_quality: str | None) -> str:
    """Choose a download/source ceiling before the final encode plan is known."""

    key = _normalise_format(format_key)
    profile = resolved_profile(key)
    requested = _quality_height(video_quality)
    cap = _PROFILE_MAX_HEIGHT[profile]
    limits = [value for value in (requested, cap) if value is not None]
    if not limits:
        return "source"
    return str(min(limits))


def _primary_video_stream(probe: dict[str, Any]) -> dict[str, Any]:
    for item in probe.get("streams", []) or []:
        if item.get("codec_type") == "video":
            return item
    return {}


def _source_height(probe: dict[str, Any]) -> int | None:
    stream = _primary_video_stream(probe)
    try:
        value = int(stream.get("height") or 0)
    except (TypeError, ValueError):
        return None
    return value or None


def _source_bitrate_kbps(probe: dict[str, Any]) -> int | None:
    stream = _primary_video_stream(probe)
    candidates = [stream.get("bit_rate"), (probe.get("format") or {}).get("bit_rate")]
    for raw in candidates:
        try:
            value = int(raw or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return max(1, value // 1000)
    return None


def _bucket_height(height: int | None) -> int:
    value = int(height or 1080)
    for candidate in _STANDARD_HEIGHTS:
        if value <= candidate:
            return candidate
    return 2160


def video_bitrate(format_key: str, height: int | None) -> str:
    profile = resolved_profile(format_key)
    if profile == "original":
        # This value is only used when an explicit resolution reduction forces an
        # encode while the format preference otherwise says Original.
        profile = "high"
    kbps = _VIDEO_KBPS[profile][_bucket_height(height)]
    return f"{kbps}k"


def audio_bitrate(format_key: str) -> str:
    profile = resolved_profile(format_key)
    return f"{_AUDIO_KBPS[profile]}k"


def output_plan(format_key: str, probe: dict[str, Any], video_quality: str | None) -> OutputPlan:
    key = _normalise_format(format_key)
    selected = requested_profile(key)
    profile = _AUTO_PROFILE[key] if selected == "auto" else selected
    stream = _primary_video_stream(probe)
    source_height = _source_height(probe)
    requested_height = _quality_height(video_quality)
    cap = _PROFILE_MAX_HEIGHT[profile]

    limits = [value for value in (source_height, requested_height, cap) if value is not None]
    target_height = min(limits) if limits else source_height or requested_height or cap

    if not stream:
        return OutputPlan(
            key,
            selected,
            profile,
            None,
            None,
            None,
            audio_bitrate(key),
            False,
            "audio-only source",
        )

    explicit_downscale = (
        source_height is not None
        and requested_height is not None
        and source_height > requested_height
    )
    profile_downscale = (
        source_height is not None
        and cap is not None
        and source_height > cap
    )

    codec = str(stream.get("codec_name") or "").lower()
    pix_fmt = str(stream.get("pix_fmt") or "").lower()
    h264_compatible = codec == "h264" and pix_fmt in {"yuv420p", "yuvj420p"}

    if profile == "original":
        encode = explicit_downscale
        reason = "explicit resolution limit" if encode else "preserve source video"
    else:
        target_bitrate = int(video_bitrate(key, target_height).rstrip("k"))
        source_bitrate = _source_bitrate_kbps(probe)
        oversized = source_bitrate is None or source_bitrate > int(target_bitrate * 1.15)
        incompatible = key in {"mp4", "share"} and not h264_compatible
        encode = explicit_downscale or profile_downscale or oversized or incompatible
        if explicit_downscale or profile_downscale:
            reason = "resolution/profile limit"
        elif incompatible:
            reason = "H.264 compatibility"
        elif oversized:
            reason = "size target"
        else:
            reason = "source already meets target"

    return OutputPlan(
        key,
        selected,
        profile,
        source_height,
        target_height,
        video_bitrate(key, target_height) if encode else None,
        audio_bitrate(key),
        encode,
        reason,
    )


def approximate_mb_per_minute(format_key: str, height: int) -> float | None:
    profile = resolved_profile(format_key)
    if profile == "original":
        return None
    video = int(video_bitrate(format_key, height).rstrip("k"))
    audio = int(audio_bitrate(format_key).rstrip("k"))
    return (video + audio) * 60.0 / 8.0 / 1000.0


def profile_summary(values: dict[str, str] | None = None) -> str:
    configured = values or load_profiles()
    lines = ["### Output profiles"]
    for key in ("mkv", "mp4", "share"):
        selected = _normalise_profile(configured.get(key))
        resolved = _AUTO_PROFILE[key] if selected == "auto" else selected
        cap = _PROFILE_MAX_HEIGHT[resolved]
        if resolved == "original":
            detail = "preserve source video unless you explicitly set a lower resolution"
        else:
            sample_height = min(cap or 1080, 1080)
            rate = approximate_mb_per_minute_for_profile(resolved, sample_height)
            detail = f"up to {cap}p · about {rate:.1f} MB/min at {sample_height}p"
        suffix = f"Auto → {resolved}" if selected == "auto" else resolved
        lines.append(f"- **{FORMAT_LABELS[key]}:** {suffix} · {detail}")
    return "\n".join(lines)


def approximate_mb_per_minute_for_profile(profile: str, height: int) -> float:
    selected = profile if profile in _VIDEO_KBPS else "balanced"
    video = _VIDEO_KBPS[selected][_bucket_height(height)]
    audio = _AUDIO_KBPS[selected]
    return (video + audio) * 60.0 / 8.0 / 1000.0
