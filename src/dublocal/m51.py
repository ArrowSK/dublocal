from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL

from . import m5
from .language_utils import normalize_language_code
from .media import DubLocalError
from .output_naming import dubbed_media_path, safe_language_suffix
from .timeline import parse_srt
from .voice_text import spoken_text


VIDEO_QUALITY_CHOICES = [
    ("Original / best available · no local video re-encode", "source"),
    ("2160p max", "2160"),
    ("1440p max", "1440"),
    ("1080p max", "1080"),
    ("720p max", "720"),
    ("480p max", "480"),
]

_VIDEO_BITRATES = {
    2160: "25M",
    1440: "16M",
    1080: "10M",
    720: "5M",
    480: "2500k",
}

MixFunction = Callable[..., Path]
TimingFunction = Callable[..., m5.TimingFit]


@dataclass(frozen=True, slots=True)
class RenderResult:
    output_path: Path
    mixed_audio_path: Path
    fitted_voice_path: Path
    source_path: Path
    mode: str
    container: str
    language: str
    video_stream_copy: bool
    original_audio_tracks: int
    output_audio_tracks: int
    timing_adjusted_segments: int
    remaining_timing_overflows: int
    embedded_subtitle_tracks: int
    video_quality: str


def _notify(callback, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), label)


def _target_height(value: str | None) -> int | None:
    if not value or value == "source":
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise DubLocalError("Choose a valid video-quality option.")
    if result not in _VIDEO_BITRATES:
        raise DubLocalError("Choose one of the offered video-quality options.")
    return result


def _youtube_format(quality: str) -> str:
    height = _target_height(quality)
    if height is None:
        return "bestvideo*+bestaudio/best"
    return f"bestvideo*[height<={height}]+bestaudio/best[height<={height}]/best"


def acquire_source_media(
    info: dict[str, Any],
    output_dir: Path,
    *,
    video_quality: str,
    progress_callback=None,
) -> Path:
    if info.get("kind") == "local":
        path = Path(str(info.get("path") or "")).expanduser().resolve()
        if not path.is_file():
            raise DubLocalError("The selected local source file no longer exists.")
        _notify(progress_callback, 0.22, "Local source ready")
        return path
    if info.get("kind") != "youtube":
        raise DubLocalError("Load a source before rendering dubbed media.")

    url = str(info.get("url") or "").strip()
    if not url:
        raise DubLocalError("The loaded YouTube source no longer has a usable URL.")

    def hook(payload: dict[str, Any]) -> None:
        if payload.get("status") != "downloading":
            return
        downloaded = float(payload.get("downloaded_bytes") or 0)
        total = float(payload.get("total_bytes") or payload.get("total_bytes_estimate") or 0)
        if total > 0:
            _notify(progress_callback, 0.03 + min(0.18, downloaded / total * 0.18), "Downloading selected YouTube quality")

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": _youtube_format(video_quality),
        "merge_output_format": "mkv",
        "outtmpl": str(output_dir / "source.%(ext)s"),
        "retries": 3,
        "fragment_retries": 3,
        "progress_hooks": [hook],
    }
    try:
        with YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        message = str(exc)
        if "429" in message or "Too Many Requests" in message:
            raise DubLocalError(
                "YouTube temporarily rate-limited source-media delivery. Wait and retry, or use a local copy you have the right to process."
            ) from exc
        raise DubLocalError(f"Could not download the selected YouTube quality: {message}") from exc

    candidates = [
        path
        for path in output_dir.glob("source.*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise DubLocalError("YouTube download completed without a usable media file.")
    candidates.sort(key=lambda item: item.stat().st_size, reverse=True)
    _notify(progress_callback, 0.22, "Selected YouTube source ready")
    return candidates[0]


def _dialogue_windows(subtitle_path: str | Path | None) -> list[tuple[float, float]]:
    if not subtitle_path:
        return []
    path = Path(subtitle_path).expanduser().resolve()
    if not path.is_file():
        return []
    try:
        segments = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []

    raw: list[tuple[float, float]] = []
    for segment in segments:
        if not spoken_text(segment.text):
            continue
        start = max(0.0, segment.start_ms / 1000.0 - 0.12)
        end = max(start, segment.end_ms / 1000.0 + 0.35)
        raw.append((start, end))
    if not raw:
        return []

    merged: list[tuple[float, float]] = [raw[0]]
    for start, end in raw[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 0.18:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _guide_expression(windows: list[tuple[float, float]]) -> str:
    return "+".join(
        f"between(t\\,{start:.3f}\\,{end:.3f})" for start, end in windows
    )


def create_dubbed_mix(
    source_media: Path,
    fitted_voice: Path,
    output_dir: Path,
    *,
    dialogue_subtitle_path: str | Path | None,
    progress_callback=None,
) -> Path:
    """Create a stronger dubbing mix using subtitle-window ducking."""

    ffmpeg = m5._require("ffmpeg")
    probe = m5._probe(source_media)
    if m5._audio_stream_count(probe) < 1:
        raise DubLocalError("The source media has no audio track to mix with the DubLocal voice track.")
    duration = m5._duration_seconds(probe)
    output = output_dir / "dubbed-mix.m4a"
    windows = _dialogue_windows(dialogue_subtitle_path)

    if windows and duration > 0:
        guide = _guide_expression(windows)
        filter_graph = (
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo[orig];"
            f"aevalsrc=exprs='{guide}':s=48000:d={duration:.3f}[dialogue_guide];"
            "[orig][dialogue_guide]sidechaincompress=threshold=0.08:ratio=12:attack=8:release=260[ducked];"
            "[1:a:0]aresample=48000,aformat=channel_layouts=stereo,volume=1.08[voice];"
            "[ducked][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "alimiter=limit=0.95[mix]"
        )
    else:
        filter_graph = (
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo[orig];"
            "[1:a:0]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice_sc][voice_mix];"
            "[orig][voice_sc]sidechaincompress=threshold=0.025:ratio=16:attack=8:release=300[ducked];"
            "[voice_mix]volume=1.08[voice_loud];"
            "[ducked][voice_loud]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "alimiter=limit=0.95[mix]"
        )

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
        str(fitted_voice),
        "-filter_complex",
        filter_graph,
        "-map",
        "[mix]",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]
    m5._run_ffmpeg_progress(
        command,
        duration_seconds=duration,
        start_fraction=0.36,
        end_fraction=0.68,
        label="Mixing dubbed soundtrack with strong dialogue suppression",
        progress_callback=progress_callback,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("FFmpeg did not create a usable dubbed soundtrack.")
    return output


def _subtitle_stream_count(probe: dict[str, Any]) -> int:
    return sum(1 for item in probe.get("streams", []) if item.get("codec_type") == "subtitle")


def _primary_video_height(probe: dict[str, Any]) -> int | None:
    for item in probe.get("streams", []):
        if item.get("codec_type") == "video":
            try:
                return int(item.get("height") or 0) or None
            except (TypeError, ValueError):
                return None
    return None


def _subtitle_language(language: str | None) -> str:
    code = normalize_language_code(language)
    if code == "auto":
        return "und"
    return m5._target_language_metadata(code)


def _external_subtitles(
    source_subtitle_path: str | Path | None,
    translated_subtitle_path: str | Path | None,
    source_language: str | None,
    translated_language: str | None,
) -> list[tuple[Path, str, str, bool]]:
    items: list[tuple[Path, str, str, bool]] = []
    seen: set[Path] = set()
    for raw, language, title, default in (
        (source_subtitle_path, source_language, "Original subtitles", False),
        (translated_subtitle_path, translated_language, "DubLocal translation", True),
    ):
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if not path.is_file() or path in seen:
            continue
        if path.suffix.lower() != ".srt":
            raise DubLocalError("Embedded DubLocal subtitle tracks currently require SRT input.")
        seen.add(path)
        items.append((path, _subtitle_language(language), title, default))
    return items


def remux_dubbed_media(
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
) -> RenderResult:
    if mode not in {"replace", "add"}:
        raise DubLocalError("Choose a valid audio-track mode.")
    if container not in {"mkv", "mp4"}:
        raise DubLocalError("Choose MKV or MP4 output.")

    ffmpeg = m5._require("ffmpeg")
    probe = m5._probe(source_media)
    audio_count = m5._audio_stream_count(probe)
    video_count = m5._video_stream_count(probe)
    duration = m5._duration_seconds(probe)
    output = dubbed_media_path(output_dir, info, language, container)
    target_lang = m5._target_language_metadata(language)
    external_subs = _external_subtitles(
        source_subtitle_path,
        translated_subtitle_path,
        source_language,
        translated_language,
    )

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

    target_height = _target_height(video_quality)
    source_height = _primary_video_height(probe)
    local_reencode = (
        bool(video_count)
        and info.get("kind") == "local"
        and target_height is not None
        and source_height is not None
        and source_height > target_height
    )

    if video_count:
        command += ["-map", "0:v:0?"]
        if local_reencode:
            command += [
                "-vf",
                f"scale=-2:{target_height}",
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                _VIDEO_BITRATES[target_height],
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
        command += ["-map", "0:a?"]
        command += ["-map", "1:a:0"]
        new_audio_index = audio_count
        output_audio_count = audio_count + 1

    preserved_subtitle_count = 0
    if container == "mkv":
        command += ["-map", "0:s?"]
        preserved_subtitle_count = _subtitle_stream_count(probe)

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

    try:
        m5._run_ffmpeg_progress(
            command,
            duration_seconds=duration,
            start_fraction=0.70,
            end_fraction=0.99,
            label=(
                "Encoding selected local video quality and remuxing tracks"
                if local_reencode
                else "Stream-copying video and remuxing audio/subtitles"
            ),
            progress_callback=progress_callback,
        )
    except DubLocalError as exc:
        message = str(exc)
        if local_reencode and "videotoolbox" in message.lower():
            raise DubLocalError(
                "The selected local video downscale needs Apple's H.264 VideoToolbox encoder, but FFmpeg could not use it. Choose Original / no re-encode or repair FFmpeg."
            ) from exc
        if container == "mp4":
            raise DubLocalError(
                f"MP4 remux was not compatible with this source ({exc}). Choose MKV to preserve the original video without re-encoding."
            ) from exc
        raise

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Remux completed without a usable output file.")

    _notify(progress_callback, 1.0, "Dubbed media ready")
    return RenderResult(
        output_path=output,
        mixed_audio_path=dubbed_audio,
        fitted_voice_path=dubbed_audio,
        source_path=source_media,
        mode=mode,
        container=container,
        language=language,
        video_stream_copy=bool(video_count) and not local_reencode,
        original_audio_tracks=audio_count,
        output_audio_tracks=output_audio_count,
        timing_adjusted_segments=0,
        remaining_timing_overflows=0,
        embedded_subtitle_tracks=len(external_subs),
        video_quality=video_quality,
    )


def render_dubbed_media(
    info: dict[str, Any],
    voice_wav: str | Path,
    language: str,
    *,
    mode: str = "replace",
    container: str = "mkv",
    video_quality: str = "source",
    source_subtitle_path: str | Path | None = None,
    translated_subtitle_path: str | Path | None = None,
    source_language: str | None = None,
    translated_language: str | None = None,
    progress_callback=None,
    mix_function: MixFunction | None = None,
    timing_function: TimingFunction | None = None,
) -> RenderResult:
    """Render dubbed media with explicit timing and mix strategy dependencies."""

    if not info:
        raise DubLocalError("Load a source before export.")
    if not language:
        raise DubLocalError("Choose/generate a voice language before export.")

    voice = Path(voice_wav).expanduser().resolve()
    if not voice.is_file():
        raise DubLocalError("Generate a voice track before export.")

    if timing_function is None:
        from .voice_timing import native_voice_timing

        timing_function = native_voice_timing
    if mix_function is None:
        mix_function = create_dubbed_mix

    job_dir = m5._new_job_dir("m51-render")
    source = acquire_source_media(
        info,
        job_dir,
        video_quality=video_quality,
        progress_callback=progress_callback,
    )
    timing = timing_function(
        voice,
        job_dir,
        maximum_speedup=1.25,
        progress_callback=progress_callback,
    )
    dialogue_timeline = source_subtitle_path or translated_subtitle_path
    mixed = mix_function(
        source,
        timing.wav_path,
        job_dir,
        dialogue_subtitle_path=dialogue_timeline,
        progress_callback=progress_callback,
    )
    remuxed = remux_dubbed_media(
        source,
        mixed,
        info,
        language,
        mode=mode,
        container=container,
        output_dir=job_dir,
        video_quality=video_quality,
        source_subtitle_path=source_subtitle_path,
        translated_subtitle_path=translated_subtitle_path,
        source_language=source_language,
        translated_language=translated_language,
        progress_callback=progress_callback,
    )
    return RenderResult(
        output_path=remuxed.output_path,
        mixed_audio_path=mixed,
        fitted_voice_path=timing.wav_path,
        source_path=source,
        mode=mode,
        container=container,
        language=language,
        video_stream_copy=remuxed.video_stream_copy,
        original_audio_tracks=remuxed.original_audio_tracks,
        output_audio_tracks=remuxed.output_audio_tracks,
        timing_adjusted_segments=timing.adjusted_segments,
        remaining_timing_overflows=timing.remaining_overflows,
        embedded_subtitle_tracks=remuxed.embedded_subtitle_tracks,
        video_quality=video_quality,
    )
