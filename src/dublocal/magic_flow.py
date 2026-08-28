from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .caption_ux import curate_caption_info
from .contextual_progress import translate_srt_contextual_with_progress
from .language_utils import normalize_language_code
from .media import DubLocalError, extract_subtitle, inspect_local_media, inspect_youtube
from .m5 import _audio_stream_count, _duration_seconds, _new_job_dir, _probe, _require, _run_ffmpeg_progress, _video_stream_count, _target_language_metadata
from .m51 import VIDEO_QUALITY_CHOICES, _primary_video_height, _target_height, acquire_source_media, render_dubbed_media
from .m53 import _VIDEO_BITRATES if False else None
from .output_naming import friendly_subtitle_path, safe_language_suffix, safe_media_stem
from .progress_operations import generate_voice_track_with_progress
from .subtitle_export import export_subtitle
from .transcription import WHISPER_MODELS, transcribe_source, whisper_model_path
from .tts import suggested_kokoro_language
from .voice_match import resolve_auto_voice_plan
from .voice_text import prepare_voice_srt


ProgressCallback = Callable[[float, str], None]

# Keep these labels intentionally non-technical. The detailed workflow remains below Magic Flow.
MAGIC_TASK_CHOICES = [
    ("Subtitles", "subtitles"),
    ("Translate", "translate"),
    ("Voice-over", "voice"),
    ("Output media file", "media"),
]
MAGIC_SUBTITLE_POLICY_CHOICES = [
    ("Auto choose · recommended", "auto"),
    ("Prefer an existing subtitle track", "existing"),
    ("Force local transcription", "local"),
]


@dataclass(frozen=True, slots=True)
class SubtitleDecision:
    method: str
    label: str
    track_value: str | None = None
    model_id: str | None = None


@dataclass(frozen=True, slots=True)
class MagicFlowResult:
    source_subtitle: Path | None
    translated_subtitle: Path | None
    voice_wav: Path | None
    media_output: Path | None
    source_language: str
    target_language: str
    decision: str
    status: str


def _notify(callback: ProgressCallback | None, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), label)


def _stage_callback(
    callback: ProgressCallback | None,
    start: float,
    end: float,
) -> ProgressCallback:
    width = max(0.0, end - start)

    def update(fraction: float, label: str) -> None:
        _notify(callback, start + max(0.0, min(1.0, fraction)) * width, label)

    return update


def inspect_magic_source(source_type: str, youtube_url: str, local_file: str | None) -> dict[str, Any]:
    if source_type == "YouTube":
        info = inspect_youtube((youtube_url or "").strip())
    else:
        if not local_file:
            raise DubLocalError("Choose a local media file first.")
        info = inspect_local_media(local_file)
    return curate_caption_info(info)


def _manual_tracks(info: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in (info.get("subtitle_tracks") or [])
        if str(item.get("source") or "").lower() != "auto"
    ]


def _automatic_tracks(info: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in (info.get("subtitle_tracks") or [])
        if str(item.get("source") or "").lower() == "auto"
    ]


def _installed_whisper(model_id: str) -> bool:
    try:
        return whisper_model_path(model_id).is_file()
    except Exception:
        return False


def recommend_subtitle_source(
    info: dict[str, Any],
    policy: str = "auto",
) -> SubtitleDecision:
    """Choose a subtitle route without surprising the user with a model download.

    Auto policy prioritizes creator/embedded text, then an already-installed Accurate
    Whisper model, then existing automatic captions, then an already-installed Base
    model. This is intentionally hardware-safe: Magic Flow never starts a multi-hundred-MiB
    model download implicitly.
    """

    manual = _manual_tracks(info)
    automatic = _automatic_tracks(info)
    accurate = "large-v3-turbo-q5_0"

    if policy == "existing":
        tracks = manual or automatic
        if tracks:
            track = tracks[0]
            return SubtitleDecision(
                "existing",
                f"Use existing · {track.get('label') or 'subtitle track'}",
                track_value=str(track.get("value")),
            )
        policy = "local"

    if policy == "local":
        for model_id in (accurate, "base", "small", "tiny"):
            if model_id in WHISPER_MODELS and _installed_whisper(model_id):
                return SubtitleDecision(
                    "transcribe",
                    f"Transcribe locally · {WHISPER_MODELS[model_id]['label']}",
                    model_id=model_id,
                )
        raise DubLocalError(
            "Magic Flow needs a local Whisper model because no existing subtitle track is being used. "
            "Open Settings → Model Manager and install Base or Accurate, then run Magic Flow again."
        )

    if manual:
        track = manual[0]
        return SubtitleDecision(
            "existing",
            f"Recommended · creator/embedded subtitles · {track.get('label') or 'track'}",
            track_value=str(track.get("value")),
        )

    # If the user already paid the storage cost for the Accurate model, use it before
    # YouTube automatic captions. This is especially valuable for songs/accents/noisy audio.
    if accurate in WHISPER_MODELS and _installed_whisper(accurate):
        return SubtitleDecision(
            "transcribe",
            f"Recommended · local {WHISPER_MODELS[accurate]['label']}",
            model_id=accurate,
        )

    if automatic:
        track = automatic[0]
        return SubtitleDecision(
            "existing",
            f"Use existing automatic captions · {track.get('label') or 'track'}",
            track_value=str(track.get("value")),
        )

    for model_id in ("base", "small", "tiny"):
        if model_id in WHISPER_MODELS and _installed_whisper(model_id):
            return SubtitleDecision(
                "transcribe",
                f"Recommended available local model · {WHISPER_MODELS[model_id]['label']}",
                model_id=model_id,
            )

    raise DubLocalError(
        "No usable existing subtitles were found and no local Whisper model is installed. "
        "Open Settings → Model Manager, install Base or Accurate, then run Magic Flow again."
    )


def _source_track_language(info: dict[str, Any], track_value: str | None) -> str:
    if not track_value:
        return "auto"
    for item in info.get("subtitle_tracks") or []:
        if str(item.get("value")) == str(track_value):
            return normalize_language_code(str(item.get("language") or "auto"))
    return "auto"


def _prepare_source_subtitle(
    info: dict[str, Any],
    decision: SubtitleDecision,
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, str]:
    if decision.method == "existing":
        _notify(progress_callback, 0.08, "Using recommended existing subtitle track")
        if not decision.track_value:
            raise DubLocalError("The recommended subtitle track is no longer available.")
        path = extract_subtitle(info, decision.track_value)
        language = _source_track_language(info, decision.track_value)
        _notify(progress_callback, 1.0, "Source subtitles ready")
    else:
        if not decision.model_id:
            raise DubLocalError("Magic Flow could not resolve a local transcription model.")
        _notify(progress_callback, 0.03, "Starting local transcription")
        result = transcribe_source(info, model_id=decision.model_id, language="auto")
        path = result.srt_path
        language = normalize_language_code(result.language)
        _notify(progress_callback, 1.0, "Local transcription ready")

    friendly = friendly_subtitle_path(path, info, language)
    return friendly, language


def _task_set(tasks: Iterable[str] | None) -> set[str]:
    return {str(item) for item in (tasks or [])}


def _video_bitrate(height: int) -> str:
    # Keep aligned with M5.1 without importing private constants across modules.
    return {2160: "25M", 1440: "16M", 1080: "10M", 720: "5M", 480: "2500k"}[height]


def _package_subtitles_only(
    info: dict[str, Any],
    source_subtitle: Path,
    translated_subtitle: Path | None,
    source_language: str,
    target_language: str,
    *,
    container: str,
    video_quality: str,
    progress_callback: ProgressCallback | None,
) -> Path:
    """Package original media with selectable DubLocal subtitle tracks and untouched audio."""

    if container not in {"mkv", "mp4"}:
        raise DubLocalError("Choose MKV or MP4 output.")

    job_dir = _new_job_dir("magic-subtitle-package")
    source = acquire_source_media(
        info,
        job_dir,
        video_quality=video_quality,
        progress_callback=_stage_callback(progress_callback, 0.00, 0.32),
    )
    probe = _probe(source)
    duration = _duration_seconds(probe)
    video_count = _video_stream_count(probe)
    target_height = _target_height(video_quality)
    source_height = _primary_video_height(probe)
    local_reencode = (
        bool(video_count)
        and info.get("kind") == "local"
        and target_height is not None
        and source_height is not None
        and source_height > target_height
    )

    suffix = safe_language_suffix(target_language if translated_subtitle else source_language)
    output = job_dir / f"{safe_media_stem(info)}.subtitles.{suffix}.{container}"
    subtitles: list[tuple[Path, str, str, bool]] = [
        (source_subtitle, source_language, "Original subtitles", translated_subtitle is None)
    ]
    if translated_subtitle is not None:
        subtitles.append((translated_subtitle, target_language, "DubLocal translation", True))

    ffmpeg = _require("ffmpeg")
    command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    for path, _lang, _title, _default in subtitles:
        command += ["-i", str(path)]

    if video_count:
        command += ["-map", "0:v:0?"]
        if local_reencode:
            assert target_height is not None
            command += [
                "-vf", f"scale=-2:{target_height}",
                "-c:v", "h264_videotoolbox",
                "-b:v", _video_bitrate(target_height),
                "-pix_fmt", "yuv420p",
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

    existing_subtitle_count = sum(1 for item in probe.get("streams", []) if item.get("codec_type") == "subtitle") if container == "mkv" else 0
    for offset, (_path, language, title, default) in enumerate(subtitles):
        index = existing_subtitle_count + offset
        lang = _target_language_metadata(normalize_language_code(language))
        command += [
            f"-metadata:s:s:{index}", f"language={lang}",
            f"-metadata:s:s:{index}", f"title={title} · {lang}",
            f"-disposition:s:{index}", "default" if default else "0",
        ]

    command += ["-progress", "pipe:1", "-nostats", str(output)]
    _run_ffmpeg_progress(
        command,
        duration_seconds=duration,
        start_fraction=0.34,
        end_fraction=0.99,
        label="Packaging original media and subtitle tracks",
        progress_callback=progress_callback,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Magic Flow subtitle packaging did not create a usable output file.")
    _notify(progress_callback, 1.0, "Media package ready")
    return output


def run_magic_flow(
    *,
    source_type: str,
    youtube_url: str,
    local_file: str | None,
    rights_confirmed: bool,
    target_language: str,
    tasks: Iterable[str] | None,
    subtitle_policy: str = "auto",
    keep_original_audio_track: bool = True,
    container: str = "mkv",
    video_quality: str = "source",
    progress_callback: ProgressCallback | None = None,
) -> MagicFlowResult:
    """Run the recommended local pipeline from one compact UI action."""

    if not rights_confirmed:
        raise DubLocalError("Confirm that you have the right or legal authority to process this media.")

    selected = _task_set(tasks)
    if not selected:
        raise DubLocalError("Choose at least one Magic Flow output.")

    target = normalize_language_code(target_language)
    if target == "auto":
        raise DubLocalError("Choose the output language for Magic Flow.")

    # Downstream steps imply their prerequisites. The UI stays simple while the engine
    # keeps the dependency graph internally consistent.
    wants_media = "media" in selected
    wants_voice = "voice" in selected
    wants_translate = "translate" in selected or wants_voice
    wants_subtitles = bool(selected) or wants_translate or wants_voice or wants_media

    _notify(progress_callback, 0.01, "Inspecting source")
    info = inspect_magic_source(source_type, youtube_url, local_file)
    decision = recommend_subtitle_source(info, subtitle_policy)
    _notify(progress_callback, 0.08, decision.label)

    source_subtitle: Path | None = None
    translated_subtitle: Path | None = None
    voice_wav: Path | None = None
    media_output: Path | None = None
    source_language = "auto"

    if wants_subtitles:
        source_subtitle, source_language = _prepare_source_subtitle(
            info,
            decision,
            progress_callback=_stage_callback(progress_callback, 0.08, 0.34),
        )
        # Make the normal subtitle download filename immediately useful even if the
        # user stops here.
        source_subtitle = Path(export_subtitle(source_subtitle, "srt"))

    if wants_translate:
        assert source_subtitle is not None
        translated = translate_srt_contextual_with_progress(
            source_subtitle,
            source_language or "auto",
            target,
            progress_callback=_stage_callback(progress_callback, 0.34, 0.62),
        )
        source_language = normalize_language_code(translated.source_language)
        translated_subtitle = friendly_subtitle_path(translated.srt_path, info, target)

    if wants_voice:
        timeline = translated_subtitle or source_subtitle
        assert timeline is not None
        voice_language = suggested_kokoro_language(target if translated_subtitle else source_language)
        if not voice_language:
            raise DubLocalError(
                f"Subtitles are ready, but the current Kokoro backend does not support voice generation for {target}. "
                "Uncheck Voice-over/Output media or choose a Kokoro-supported output language."
            )
        cleaned = prepare_voice_srt(timeline)
        fallback_voice, segment_voices, _summary = resolve_auto_voice_plan(
            cleaned,
            info,
            voice_language,
            progress_callback=_stage_callback(progress_callback, 0.62, 0.68),
        )
        voice = generate_voice_track_with_progress(
            cleaned,
            language=voice_language,
            voice=fallback_voice,
            speed=1.0,
            segment_voices=segment_voices,
            progress_callback=_stage_callback(progress_callback, 0.68, 0.82),
        )
        voice_wav = voice.wav_path

    if wants_media:
        if wants_voice:
            assert voice_wav is not None
            # "Keep original audio" means keep the untouched source track as a separate
            # selectable stream in addition to the balanced DubLocal mix.
            mode = "add" if keep_original_audio_track else "replace"
            rendered = render_dubbed_media(
                info,
                voice_wav,
                target if translated_subtitle else source_language,
                mode=mode,
                container=container,
                video_quality=video_quality,
                source_subtitle_path=source_subtitle,
                translated_subtitle_path=translated_subtitle,
                source_language=source_language,
                translated_language=target if translated_subtitle else None,
                progress_callback=_stage_callback(progress_callback, 0.82, 1.0),
            )
            media_output = rendered.output_path
        else:
            assert source_subtitle is not None
            media_output = _package_subtitles_only(
                info,
                source_subtitle,
                translated_subtitle,
                source_language,
                target,
                container=container,
                video_quality=video_quality,
                progress_callback=_stage_callback(progress_callback, 0.62 if wants_translate else 0.34, 1.0),
            )

    outputs: list[str] = []
    if source_subtitle:
        outputs.append(f"source subtitles: {source_subtitle.name}")
    if translated_subtitle:
        outputs.append(f"translation: {translated_subtitle.name}")
    if voice_wav:
        outputs.append(f"voice: {voice_wav.name}")
    if media_output:
        outputs.append(f"media: {media_output.name}")

    _notify(progress_callback, 1.0, "Magic Flow complete")
    status = "✓ Magic Flow complete · " + " · ".join(outputs)
    return MagicFlowResult(
        source_subtitle=source_subtitle,
        translated_subtitle=translated_subtitle,
        voice_wav=voice_wav,
        media_output=media_output,
        source_language=source_language,
        target_language=target,
        decision=decision.label,
        status=status,
    )
