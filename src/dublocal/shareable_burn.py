from __future__ import annotations

import shutil
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterable

from . import batch_flow, magic_flow
from .media import DubLocalError
from .output_naming import safe_language_suffix, safe_media_stem


_BURN_MARKER = "burn-share-subs"
_BURN_SHAREABLE = ContextVar("dublocal_burn_shareable_subtitles", default=False)
_INSTALLED = False
_ORIGINAL_RUN_MAGIC_FLOW = magic_flow.run_magic_flow
_ORIGINAL_MAKE_SHAREABLE = magic_flow._make_shareable_media


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


def _burned_shareable_media(
    source_media: str | Path,
    info: dict[str, Any],
    language: str,
    *,
    subtitle_path: str | Path | None,
    video_quality: str,
    progress_callback=None,
) -> Path:
    source = Path(source_media).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("The rendered media is no longer available for shareable export.")
    if not subtitle_path:
        raise DubLocalError("Burn-in was selected, but no subtitle timeline is available.")

    subtitle = Path(subtitle_path).expanduser().resolve()
    if not subtitle.is_file() or subtitle.suffix.lower() != ".srt":
        raise DubLocalError("Shareable subtitle burn-in requires the generated SRT subtitle file.")

    probe = magic_flow._probe(source)
    duration = magic_flow._duration_seconds(probe)
    video_stream = magic_flow._primary_stream(probe, "video")
    audio_stream = magic_flow._primary_stream(probe, "audio")
    if not video_stream:
        raise DubLocalError("Subtitle burn-in needs a video stream. Choose normal Shareable MP4 for audio-only media.")

    target_height = magic_flow._target_height(video_quality)
    source_height = magic_flow._primary_video_height(probe)
    scale_height = (
        target_height
        if target_height is not None and source_height is not None and source_height > target_height
        else None
    )

    output_dir = magic_flow._new_job_dir("magic-share-burn")
    burn_srt = output_dir / "burn.srt"
    shutil.copy2(subtitle, burn_srt)
    suffix = safe_language_suffix(language)
    output = output_dir / f"{safe_media_stem(info)}.share-burned.{suffix}.mp4"
    ffmpeg = magic_flow._require("ffmpeg")

    filters: list[str] = []
    if scale_height is not None:
        filters.append(f"scale=-2:{scale_height}")
    filters.append(f"subtitles=filename='{_filter_escape(burn_srt)}':charenc=UTF-8")

    effective_height = scale_height or source_height
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        ",".join(filters),
        "-c:v",
        "h264_videotoolbox",
        "-b:v",
        magic_flow._shareable_video_bitrate(effective_height),
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
            "192k",
            "-ac",
            "2",
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

    def run(current: list[str], label: str) -> None:
        magic_flow._run_ffmpeg_progress(
            current,
            duration_seconds=duration,
            start_fraction=0.02,
            end_fraction=0.99,
            label=label,
            progress_callback=progress_callback,
        )

    try:
        run(command, "Burning subtitles into shareable MP4")
    except DubLocalError as exc:
        fallback = list(command)
        if "h264_videotoolbox" not in fallback:
            raise
        fallback[fallback.index("h264_videotoolbox")] = "libx264"
        try:
            run(fallback, "Burning subtitles into shareable MP4 · software H.264 fallback")
        except DubLocalError as fallback_exc:
            raise DubLocalError(
                f"Could not burn subtitles into the shareable H.264/AAC MP4 ({fallback_exc}). "
                "The standalone SRT remains available."
            ) from exc

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Shareable subtitle burn-in completed without a usable MP4.")
    magic_flow._notify(progress_callback, 1.0, "Shareable MP4 with burned subtitles ready")
    return output


def _make_shareable_with_optional_burn(*args: Any, **kwargs: Any) -> Path:
    if not _BURN_SHAREABLE.get():
        return _ORIGINAL_MAKE_SHAREABLE(*args, **kwargs)
    subtitle_path = kwargs.get("subtitle_path")
    return _burned_shareable_media(
        args[0] if args else kwargs["source_media"],
        args[1] if len(args) > 1 else kwargs["info"],
        args[2] if len(args) > 2 else kwargs["language"],
        subtitle_path=subtitle_path,
        video_quality=str(kwargs.get("video_quality") or "source"),
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
