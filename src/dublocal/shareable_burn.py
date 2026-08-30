from __future__ import annotations

import shutil
import subprocess
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterable

from . import batch_flow, magic_flow
from .language_utils import normalize_language_code
from .media import DubLocalError
from .output_naming import safe_language_suffix, safe_media_stem


_BURN_MARKER = "burn-share-subs"
_BURN_SHAREABLE = ContextVar("dublocal_burn_shareable_subtitles", default=False)
_INSTALLED = False
_ORIGINAL_RUN_MAGIC_FLOW = magic_flow.run_magic_flow

_COMPACT_VIDEO_BITRATES = {
    2160: "6000k",
    1440: "4500k",
    1080: "3000k",
    720: "1800k",
    480: "900k",
}
_COMPACT_AUDIO_BITRATE = "160k"


def _strip_burn_marker(tasks: Iterable[str] | None) -> tuple[bool, list[str]]:
    values = [str(item) for item in (tasks or [])]
    burn = _BURN_MARKER in values
    return burn, [item for item in values if item != _BURN_MARKER]


def _filter_escape(path: Path) -> str:
    # libavfilter uses its own escaping even inside quotes.
    value = str(path)
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(";", "\\;")
    )


def _compact_video_bitrate(height: int | None) -> str:
    value = int(height or 1080)
    for candidate in (2160, 1440, 1080, 720, 480):
        if value >= candidate:
            return _COMPACT_VIDEO_BITRATES[candidate]
    return _COMPACT_VIDEO_BITRATES[480]


def _ffmpeg_supports_filter(ffmpeg: str, filter_name: str) -> bool:
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        if filter_name in line.split():
            return True
    return False


def _subtitle_capable_ffmpeg(preferred: str) -> str | None:
    candidates = [preferred, "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    seen: set[str] = set()
    for raw in candidates:
        resolved = shutil.which(raw) if "/" not in raw else raw
        if not resolved or resolved in seen or not Path(resolved).is_file():
            continue
        seen.add(resolved)
        if _ffmpeg_supports_filter(resolved, "subtitles"):
            return resolved
    return None


def _shareable_media(
    source_media: str | Path,
    info: dict[str, Any],
    language: str,
    *,
    subtitle_path: str | Path | None,
    subtitle_language: str | None,
    video_quality: str,
    burn_subtitles: bool,
    progress_callback=None,
) -> Path:
    source = Path(source_media).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("The rendered media is no longer available for shareable export.")

    subtitle: Path | None = None
    if subtitle_path:
        candidate = Path(subtitle_path).expanduser().resolve()
        if candidate.is_file() and candidate.suffix.lower() == ".srt":
            subtitle = candidate
    if burn_subtitles and subtitle is None:
        raise DubLocalError("Burn-in was selected, but no generated SRT subtitle file is available.")

    probe = magic_flow._probe(source)
    duration = magic_flow._duration_seconds(probe)
    video_stream = magic_flow._primary_stream(probe, "video")
    audio_stream = magic_flow._primary_stream(probe, "audio")
    if burn_subtitles and not video_stream:
        raise DubLocalError(
            "Subtitle burn-in needs a video stream. Choose normal Shareable MP4 for audio-only media."
        )

    target_height = magic_flow._target_height(video_quality)
    source_height = magic_flow._primary_video_height(probe)
    if target_height is None and source_height is not None and source_height > 1080:
        # Shareable is a delivery copy rather than the archival master. Explicit
        # 1440p/2160p choices remain available, but the default/source preset caps
        # very large sources at 1080p so a 4K input does not silently stay huge.
        scale_height = 1080
    else:
        scale_height = (
            target_height
            if target_height is not None
            and source_height is not None
            and source_height > target_height
            else None
        )

    output_dir = magic_flow._new_job_dir(
        "magic-share-burn" if burn_subtitles else "magic-share"
    )
    suffix = safe_language_suffix(language)
    if burn_subtitles:
        output = output_dir / f"{safe_media_stem(info)}.share-burned.{suffix}.mp4"
    else:
        output = output_dir / f"{safe_media_stem(info)}.share.{suffix}.mp4"

    ffmpeg = magic_flow._require("ffmpeg")
    burn_srt: Path | None = None
    if burn_subtitles:
        capable = _subtitle_capable_ffmpeg(ffmpeg)
        if capable is None:
            raise DubLocalError(
                "This FFmpeg build cannot render subtitles because its 'subtitles' filter is missing. "
                "Reopen DubLocal and accept the FFmpeg repair prompt, then retry. "
                "The standalone SRT remains available."
            )
        ffmpeg = capable
        burn_srt = output_dir / "burn.srt"
        shutil.copy2(subtitle, burn_srt)

    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
    ]

    if subtitle is not None and not burn_subtitles:
        command += ["-i", str(subtitle)]

    if video_stream:
        command += ["-map", "0:v:0"]
        filters: list[str] = []
        if scale_height is not None:
            filters.append(f"scale=-2:{scale_height}")
        if burn_srt is not None:
            filters.append(
                f"subtitles=filename='{_filter_escape(burn_srt)}':charenc=UTF-8"
            )
        if filters:
            command += ["-vf", ",".join(filters)]

        effective_height = scale_height or source_height
        command += [
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            _compact_video_bitrate(effective_height),
            "-pix_fmt",
            "yuv420p",
            "-tag:v",
            "avc1",
        ]

    if audio_stream:
        command += [
            "-map",
            "0:a:0",
            "-c:a",
            "aac",
            "-b:a",
            _COMPACT_AUDIO_BITRATE,
            "-ac",
            "2",
        ]

    if subtitle is not None and not burn_subtitles:
        command += ["-map", "1:0", "-c:s", "mov_text"]
        lang = magic_flow._target_language_metadata(
            normalize_language_code(subtitle_language or language)
        )
        command += [
            "-metadata:s:s:0",
            f"language={lang}",
            "-metadata:s:s:0",
            f"title=DubLocal subtitles · {lang}",
            "-disposition:s:0",
            "default",
        ]

    command += [
        "-map_metadata",
        "0",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]

    label = (
        "Burning subtitles into compact shareable MP4"
        if burn_subtitles
        else "Creating compact shareable MP4"
    )

    def run(current: list[str], current_label: str) -> None:
        magic_flow._run_ffmpeg_progress(
            current,
            duration_seconds=duration,
            start_fraction=0.02,
            end_fraction=0.99,
            label=current_label,
            progress_callback=progress_callback,
        )

    try:
        run(command, label)
    except DubLocalError as exc:
        fallback = list(command)
        if "h264_videotoolbox" not in fallback:
            raise
        fallback[fallback.index("h264_videotoolbox")] = "libx264"
        fallback_label = f"{label} · software H.264 fallback"
        try:
            run(fallback, fallback_label)
        except DubLocalError as fallback_exc:
            if burn_subtitles:
                raise DubLocalError(
                    f"Could not burn subtitles into the compact shareable H.264/AAC MP4 "
                    f"({fallback_exc}). The standalone SRT remains available."
                ) from exc
            raise DubLocalError(
                f"Could not create the compact shareable H.264/AAC MP4 ({fallback_exc}). "
                "The normal MKV output remains the safest archival format."
            ) from exc

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Shareable MP4 export completed without a usable file.")
    magic_flow._notify(
        progress_callback,
        1.0,
        "Shareable MP4 with burned subtitles ready"
        if burn_subtitles
        else "Compact shareable MP4 ready",
    )
    return output


def _burned_shareable_media(
    source_media: str | Path,
    info: dict[str, Any],
    language: str,
    *,
    subtitle_path: str | Path | None,
    video_quality: str,
    progress_callback=None,
) -> Path:
    return _shareable_media(
        source_media,
        info,
        language,
        subtitle_path=subtitle_path,
        subtitle_language=language,
        video_quality=video_quality,
        burn_subtitles=True,
        progress_callback=progress_callback,
    )


def _make_shareable_with_optional_burn(*args: Any, **kwargs: Any) -> Path:
    return _shareable_media(
        args[0] if args else kwargs["source_media"],
        args[1] if len(args) > 1 else kwargs["info"],
        args[2] if len(args) > 2 else kwargs["language"],
        subtitle_path=kwargs.get("subtitle_path"),
        subtitle_language=kwargs.get("subtitle_language"),
        video_quality=str(kwargs.get("video_quality") or "source"),
        burn_subtitles=_BURN_SHAREABLE.get(),
        progress_callback=kwargs.get("progress_callback"),
    )


def _run_magic_flow_with_optional_burn(*args: Any, **kwargs: Any):
    burn, cleaned = _strip_burn_marker(kwargs.get("tasks"))
    updated = dict(kwargs)
    updated["tasks"] = cleaned
    token = _BURN_SHAREABLE.set(burn)
    try:
        return _ORIGINAL_RUN_MAGIC_FLOW(*args, **updated)
    finally:
        _BURN_SHAREABLE.reset(token)


def install_shareable_burn_refinement() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # run_magic_flow resolves _make_shareable_media from its module globals at runtime,
    # so this remains a narrow share-export refinement rather than a pipeline rewrite.
    magic_flow._make_shareable_media = _make_shareable_with_optional_burn
    magic_flow.run_magic_flow = _run_magic_flow_with_optional_burn
    batch_flow.run_magic_flow = _run_magic_flow_with_optional_burn
