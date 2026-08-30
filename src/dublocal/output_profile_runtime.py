from __future__ import annotations

import shutil
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from . import m51, magic_flow
from .language_utils import normalize_language_code
from .media import DubLocalError
from .output_naming import safe_language_suffix, safe_media_stem
from .output_profiles import (
    acquisition_quality,
    audio_bitrate,
    output_plan,
    video_bitrate,
)


_CURRENT_OUTPUT_FORMAT = ContextVar("dublocal_output_format", default="mkv")
_INSTALLED = False
_ORIGINAL_RUN_MAGIC_FLOW = magic_flow.run_magic_flow


def _effective_format(explicit: str | None = None) -> str:
    current = _CURRENT_OUTPUT_FORMAT.get()
    if current in {"mkv", "mp4", "share"}:
        return current
    value = str(explicit or "mkv").lower()
    return value if value in {"mkv", "mp4", "share"} else "mkv"


def _run_magic_flow_profiled(*args: Any, **kwargs: Any):
    """Apply the saved per-format Auto/profile ceiling before media acquisition."""

    updated = dict(kwargs)
    container = str(updated.get("container") or "mkv").lower()
    if container not in {"mkv", "mp4", "share"}:
        container = "mkv"
    requested_quality = str(updated.get("video_quality") or "source")
    updated["video_quality"] = acquisition_quality(container, requested_quality)

    token = _CURRENT_OUTPUT_FORMAT.set(container)
    try:
        return _ORIGINAL_RUN_MAGIC_FLOW(*args, **updated)
    finally:
        _CURRENT_OUTPUT_FORMAT.reset(token)


def _ffmpeg_run_with_h264_fallback(
    command: list[str],
    *,
    duration: float,
    start: float,
    end: float,
    label: str,
    progress_callback=None,
) -> None:
    try:
        magic_flow._run_ffmpeg_progress(
            command,
            duration_seconds=duration,
            start_fraction=start,
            end_fraction=end,
            label=label,
            progress_callback=progress_callback,
        )
    except DubLocalError as exc:
        if "h264_videotoolbox" not in command:
            raise
        fallback = list(command)
        fallback[fallback.index("h264_videotoolbox")] = "libx264"
        try:
            magic_flow._run_ffmpeg_progress(
                fallback,
                duration_seconds=duration,
                start_fraction=start,
                end_fraction=end,
                label=f"{label} · software H.264 fallback",
                progress_callback=progress_callback,
            )
        except DubLocalError as fallback_exc:
            raise DubLocalError(f"{label} failed ({fallback_exc}).") from exc


def _make_shareable_media_profiled(
    source_media: str | Path,
    info: dict[str, Any],
    language: str,
    *,
    subtitle_path: str | Path | None = None,
    subtitle_language: str | None = None,
    video_quality: str = "source",
    progress_callback=None,
) -> Path:
    source = Path(source_media).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("The rendered media is no longer available for shareable export.")

    probe = magic_flow._probe(source)
    duration = magic_flow._duration_seconds(probe)
    video_stream = magic_flow._primary_stream(probe, "video")
    audio_stream = magic_flow._primary_stream(probe, "audio")
    plan = output_plan("share", probe, video_quality)

    output_dir = magic_flow._new_job_dir("magic-share")
    suffix = safe_language_suffix(language)
    output = output_dir / f"{safe_media_stem(info)}.share.{suffix}.mp4"
    ffmpeg = magic_flow._require("ffmpeg")
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

    subtitle: Path | None = None
    if subtitle_path:
        candidate = Path(subtitle_path).expanduser().resolve()
        if candidate.is_file() and candidate.suffix.lower() == ".srt":
            subtitle = candidate
            command += ["-i", str(candidate)]

    encode_video = False
    if video_stream:
        command += ["-map", "0:v:0"]
        if plan.encode_video:
            encode_video = True
            if (
                plan.target_height is not None
                and plan.source_height is not None
                and plan.source_height > plan.target_height
            ):
                command += ["-vf", f"scale=-2:{plan.target_height}"]
            command += [
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                plan.video_bitrate or video_bitrate("share", plan.target_height),
                "-pix_fmt",
                "yuv420p",
                "-tag:v",
                "avc1",
            ]
        else:
            command += ["-c:v", "copy"]

    if audio_stream:
        command += [
            "-map",
            "0:a:0",
            "-c:a",
            "aac",
            "-b:a",
            plan.audio_bitrate,
            "-ac",
            "2",
        ]

    if subtitle is not None:
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

    if encode_video:
        _ffmpeg_run_with_h264_fallback(
            command,
            duration=duration,
            start=0.02,
            end=0.99,
            label="Creating compact Shareable MP4",
            progress_callback=progress_callback,
        )
    else:
        magic_flow._run_ffmpeg_progress(
            command,
            duration_seconds=duration,
            start_fraction=0.02,
            end_fraction=0.99,
            label="Creating Shareable MP4",
            progress_callback=progress_callback,
        )

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Shareable MP4 export completed without a usable file.")
    magic_flow._notify(progress_callback, 1.0, "Shareable MP4 ready")
    return output


def _package_subtitles_only_profiled(
    info: dict[str, Any],
    source_subtitle: Path,
    translated_subtitle: Path | None,
    source_language: str,
    target_language: str,
    *,
    container: str,
    video_quality: str,
    progress_callback,
) -> Path:
    if container not in {"mkv", "mp4"}:
        raise DubLocalError("Choose MKV or MP4 output.")

    output_format = _effective_format(container)
    job_dir = magic_flow._new_job_dir("magic-subtitle-package")
    source = m51.acquire_source_media(
        info,
        job_dir,
        video_quality=video_quality,
        progress_callback=magic_flow._stage_callback(progress_callback, 0.00, 0.32),
    )
    probe = magic_flow._probe(source)
    duration = magic_flow._duration_seconds(probe)
    video_count = magic_flow._video_stream_count(probe)
    plan = output_plan(output_format, probe, video_quality)

    suffix = safe_language_suffix(target_language if translated_subtitle else source_language)
    output = job_dir / f"{safe_media_stem(info)}.subtitles.{suffix}.{container}"
    subtitles: list[tuple[Path, str, str, bool]] = [
        (source_subtitle, source_language, "Original subtitles", translated_subtitle is None)
    ]
    if translated_subtitle is not None:
        subtitles.append((translated_subtitle, target_language, "DubLocal translation", True))

    ffmpeg = magic_flow._require("ffmpeg")
    command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    for path, _lang, _title, _default in subtitles:
        command += ["-i", str(path)]

    if video_count:
        command += ["-map", "0:v:0?"]
        if plan.encode_video:
            if (
                plan.target_height is not None
                and plan.source_height is not None
                and plan.source_height > plan.target_height
            ):
                command += ["-vf", f"scale=-2:{plan.target_height}"]
            command += [
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                plan.video_bitrate or video_bitrate(output_format, plan.target_height),
                "-pix_fmt",
                "yuv420p",
            ]
        else:
            command += ["-c:v", "copy"]

    command += ["-map", "0:a?", "-c:a", "copy"]
    if container == "mkv":
        command += ["-map", "0:s?", "-c:s", "copy"]
    for offset, _item in enumerate(subtitles, start=1):
        command += ["-map", f"{offset}:0"]
    if container == "mp4":
        command += ["-c:s", "mov_text", "-movflags", "+faststart"]

    existing_subtitle_count = (
        sum(1 for item in probe.get("streams", []) if item.get("codec_type") == "subtitle")
        if container == "mkv"
        else 0
    )
    for offset, (_path, language, title, default) in enumerate(subtitles):
        index = existing_subtitle_count + offset
        lang = magic_flow._target_language_metadata(normalize_language_code(language))
        command += [
            f"-metadata:s:s:{index}",
            f"language={lang}",
            f"-metadata:s:s:{index}",
            f"title={title} · {lang}",
            f"-disposition:s:{index}",
            "default" if default else "0",
        ]

    command += ["-progress", "pipe:1", "-nostats", str(output)]
    if plan.encode_video:
        _ffmpeg_run_with_h264_fallback(
            command,
            duration=duration,
            start=0.34,
            end=0.99,
            label="Encoding output profile and packaging subtitles",
            progress_callback=progress_callback,
        )
    else:
        magic_flow._run_ffmpeg_progress(
            command,
            duration_seconds=duration,
            start_fraction=0.34,
            end_fraction=0.99,
            label="Packaging original media and subtitle tracks",
            progress_callback=progress_callback,
        )

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Subtitle packaging did not create a usable output file.")
    magic_flow._notify(progress_callback, 1.0, "Media package ready")
    return output


def _remux_dubbed_media_profiled(
    source_media: Path,
    dubbed_audio: Path,
    info: dict[str, Any],
    language: str,
    *,
    mode: str,
    container: str,
    output_dir: Path,
    video_quality: str,
    source_subtitle_path: str | Path | None,
    translated_subtitle_path: str | Path | None,
    source_language: str | None,
    translated_language: str | None,
    progress_callback=None,
):
    if mode not in {"replace", "add"}:
        raise DubLocalError("Choose a valid audio-track mode.")
    if container not in {"mkv", "mp4"}:
        raise DubLocalError("Choose MKV or MP4 output.")

    output_format = _effective_format(container)
    ffmpeg = m51.m5._require("ffmpeg")
    probe = m51.m5._probe(source_media)
    audio_count = m51.m5._audio_stream_count(probe)
    video_count = m51.m5._video_stream_count(probe)
    duration = m51.m5._duration_seconds(probe)
    output = m51.dubbed_media_path(output_dir, info, language, container)
    target_lang = m51.m5._target_language_metadata(language)
    external_subs = m51._external_subtitles(
        source_subtitle_path,
        translated_subtitle_path,
        source_language,
        translated_language,
    )
    plan = output_plan(output_format, probe, video_quality)

    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_media),
        "-i",
        str(dubbed_audio),
    ]
    for path, _lang, _title, _default in external_subs:
        command += ["-i", str(path)]

    if video_count:
        command += ["-map", "0:v:0?"]
        if plan.encode_video:
            if (
                plan.target_height is not None
                and plan.source_height is not None
                and plan.source_height > plan.target_height
            ):
                command += ["-vf", f"scale=-2:{plan.target_height}"]
            command += [
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                plan.video_bitrate or video_bitrate(output_format, plan.target_height),
                "-pix_fmt",
                "yuv420p",
            ]
        else:
            command += ["-c:v", "copy"]

    if mode == "replace":
        command += ["-map", "1:a:0"]
        for index in range(1, audio_count):
            command += ["-map", f"0:a:{index}?"]
        new_audio_index = 0
        output_audio_count = max(1, audio_count)
    else:
        command += ["-map", "0:a?", "-map", "1:a:0"]
        new_audio_index = audio_count
        output_audio_count = audio_count + 1

    preserved_subtitle_count = 0
    if container == "mkv":
        command += ["-map", "0:s?"]
        preserved_subtitle_count = m51._subtitle_stream_count(probe)

    first_external_input = 2
    for offset, _item in enumerate(external_subs):
        command += ["-map", f"{first_external_input + offset}:0"]

    command += [
        "-c:a",
        "copy",
        "-map_metadata",
        "0",
        f"-metadata:s:a:{new_audio_index}",
        f"language={target_lang}",
        f"-metadata:s:a:{new_audio_index}",
        f"title=DubLocal · {safe_language_suffix(language)}",
    ]
    if mode == "replace":
        command += ["-disposition:a:0", "default"]
        for index in range(1, output_audio_count):
            command += [f"-disposition:a:{index}", "0"]
    else:
        command += [f"-disposition:a:{new_audio_index}", "0"]

    if container == "mkv":
        command += ["-c:s", "copy"]
    elif external_subs:
        command += ["-c:s", "mov_text"]

    for offset, (_path, lang, title, default) in enumerate(external_subs):
        subtitle_index = preserved_subtitle_count + offset if container == "mkv" else offset
        command += [
            f"-metadata:s:s:{subtitle_index}",
            f"language={lang}",
            f"-metadata:s:s:{subtitle_index}",
            f"title={title} · {lang}",
            f"-disposition:s:{subtitle_index}",
            "default" if default else "0",
        ]

    if container == "mp4":
        command += ["-movflags", "+faststart"]
    command += ["-progress", "pipe:1", "-nostats", str(output)]

    if plan.encode_video:
        _ffmpeg_run_with_h264_fallback(
            command,
            duration=duration,
            start=0.70,
            end=0.99,
            label="Encoding selected output profile and remuxing tracks",
            progress_callback=progress_callback,
        )
    else:
        m51.m5._run_ffmpeg_progress(
            command,
            duration_seconds=duration,
            start_fraction=0.70,
            end_fraction=0.99,
            label="Stream-copying video and remuxing audio/subtitles",
            progress_callback=progress_callback,
        )

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Remux completed without a usable output file.")

    m51._notify(progress_callback, 1.0, "Dubbed media ready")
    return m51.RenderResult(
        output_path=output,
        mixed_audio_path=dubbed_audio,
        fitted_voice_path=dubbed_audio,
        source_path=source_media,
        mode=mode,
        container=container,
        language=language,
        video_stream_copy=bool(video_count) and not plan.encode_video,
        original_audio_tracks=audio_count,
        output_audio_tracks=output_audio_count,
        timing_adjusted_segments=0,
        remaining_timing_overflows=0,
        embedded_subtitle_tracks=len(external_subs),
        video_quality=video_quality,
    )


def _burned_shareable_media_profiled(shareable_burn):
    def burn(
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

        plan = output_plan("share", probe, video_quality)
        output_dir = magic_flow._new_job_dir("magic-share-burn")
        burn_srt = output_dir / "burn.srt"
        shutil.copy2(subtitle, burn_srt)
        suffix = safe_language_suffix(language)
        output = output_dir / f"{safe_media_stem(info)}.share-burned.{suffix}.mp4"
        ffmpeg = shareable_burn._burn_ffmpeg()

        filters: list[str] = []
        if (
            plan.target_height is not None
            and plan.source_height is not None
            and plan.source_height > plan.target_height
        ):
            filters.append(f"scale=-2:{plan.target_height}")
        filters.append(
            f"subtitles=filename='{shareable_burn._filter_escape(burn_srt)}':charenc=UTF-8"
        )

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
            video_bitrate("share", plan.target_height),
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
                audio_bitrate("share"),
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
            run(command, "Burning subtitles into compact Shareable MP4")
        except DubLocalError as exc:
            if shareable_burn._is_missing_filter_error(exc):
                raise DubLocalError(
                    "The selected FFmpeg build reported that its subtitles/libass filter is unavailable. "
                    "Update/reopen DubLocal and allow the optional ffmpeg-full setup. "
                    "The standalone SRT remains available."
                ) from exc
            fallback = list(command)
            if "h264_videotoolbox" not in fallback:
                raise
            fallback[fallback.index("h264_videotoolbox")] = "libx264"
            try:
                run(fallback, "Burning subtitles into compact Shareable MP4 · software H.264 fallback")
            except DubLocalError as fallback_exc:
                raise DubLocalError(
                    f"Could not burn subtitles into the Shareable MP4 ({fallback_exc}). "
                    "The standalone SRT remains available."
                ) from exc

        if not output.is_file() or output.stat().st_size == 0:
            raise DubLocalError("Shareable subtitle burn-in completed without a usable MP4.")
        magic_flow._notify(progress_callback, 1.0, "Shareable MP4 with burned subtitles ready")
        return output

    return burn


def install_output_profile_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    magic_flow.run_magic_flow = _run_magic_flow_profiled
    magic_flow._make_shareable_media = _make_shareable_media_profiled
    magic_flow._package_subtitles_only = _package_subtitles_only_profiled
    magic_flow._shareable_video_bitrate = lambda height: video_bitrate("share", height)
    m51.remux_dubbed_media = _remux_dubbed_media_profiled


def install_shareable_burn_profile_runtime(shareable_burn) -> None:
    shareable_burn._burned_shareable_media = _burned_shareable_media_profiled(shareable_burn)
