from __future__ import annotations

from pathlib import Path
from typing import Iterable

from . import m51, magic_flow, output_profile_runtime, shareable_burn
from .adaptive_audio import create_adaptive_dubbed_mix
from .contextual_progress import translate_srt_contextual_with_progress
from .language_utils import normalize_language_code
from .media import DubLocalError
from .output_profiles import acquisition_quality
from .progress_operations import generate_voice_track_with_progress
from .subtitle_export import export_subtitle
from .voice_engine import suggested_voice_language
from .voice_selection import resolve_auto_voice_plan
from .voice_text import prepare_voice_srt
from .voice_timing import native_voice_timing


ProgressCallback = magic_flow.ProgressCallback
MagicFlowResult = magic_flow.MagicFlowResult
BURN_SHARE_SUBTITLES = "burn-share-subs"


def _profiled_render(
    info: dict,
    voice_wav: str | Path,
    language: str,
    *,
    mode: str,
    container: str,
    output_format: str,
    video_quality: str,
    source_subtitle_path: str | Path | None,
    translated_subtitle_path: str | Path | None,
    source_language: str | None,
    translated_language: str | None,
    mix_strategy: str,
    progress_callback: ProgressCallback | None,
) -> m51.RenderResult:
    """Render one media output with explicit timing, mixing and output-profile services."""

    if not info:
        raise DubLocalError("Load a source before export.")
    voice = Path(voice_wav).expanduser().resolve()
    if not voice.is_file():
        raise DubLocalError("Generate a voice track before export.")

    job_dir = m51.m5._new_job_dir("production-render")
    source = m51.acquire_source_media(
        info,
        job_dir,
        video_quality=acquisition_quality(output_format, video_quality),
        progress_callback=progress_callback,
    )
    timing = native_voice_timing(
        voice,
        job_dir,
        maximum_speedup=1.25,
        progress_callback=progress_callback,
    )
    dialogue_timeline = source_subtitle_path or translated_subtitle_path
    mixed = create_adaptive_dubbed_mix(
        source,
        timing.wav_path,
        job_dir,
        dialogue_subtitle_path=dialogue_timeline,
        progress_callback=progress_callback,
        source_info=info,
        mix_strategy=mix_strategy,
    )

    token = output_profile_runtime._CURRENT_OUTPUT_FORMAT.set(output_format)
    try:
        remuxed = output_profile_runtime._remux_dubbed_media_profiled(
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
    finally:
        output_profile_runtime._CURRENT_OUTPUT_FORMAT.reset(token)

    return m51.RenderResult(
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


def _profiled_subtitle_package(
    info: dict,
    source_subtitle: Path,
    translated_subtitle: Path | None,
    source_language: str,
    target_language: str,
    *,
    container: str,
    output_format: str,
    video_quality: str,
    progress_callback: ProgressCallback | None,
) -> Path:
    token = output_profile_runtime._CURRENT_OUTPUT_FORMAT.set(output_format)
    try:
        return output_profile_runtime._package_subtitles_only_profiled(
            info,
            source_subtitle,
            translated_subtitle,
            source_language,
            target_language,
            container=container,
            video_quality=acquisition_quality(output_format, video_quality),
            progress_callback=progress_callback,
        )
    finally:
        output_profile_runtime._CURRENT_OUTPUT_FORMAT.reset(token)


def _shareable_export(
    source_media: Path,
    info: dict,
    language: str,
    *,
    subtitle_path: Path | None,
    subtitle_language: str,
    video_quality: str,
    burn_subtitles: bool,
    progress_callback: ProgressCallback | None,
) -> Path:
    if burn_subtitles:
        burn = output_profile_runtime._burned_shareable_media_profiled(shareable_burn)
        return burn(
            source_media,
            info,
            language,
            subtitle_path=subtitle_path,
            video_quality=video_quality,
            progress_callback=progress_callback,
        )
    return output_profile_runtime._make_shareable_media_profiled(
        source_media,
        info,
        language,
        subtitle_path=subtitle_path,
        subtitle_language=subtitle_language,
        video_quality=video_quality,
        progress_callback=progress_callback,
    )


def run_standard_workflow(
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
    """Canonical production workflow.

    Dependencies are selected explicitly per job. No module function, class or Gradio
    constructor is replaced before, during or after processing.
    """

    if not rights_confirmed:
        raise DubLocalError("Confirm that you have the right or legal authority to process this media.")

    selected = {str(item) for item in (tasks or [])}
    burn_subtitles = BURN_SHARE_SUBTITLES in selected
    selected.discard(BURN_SHARE_SUBTITLES)
    single_voice = "single-voice" in selected
    selected.discard("single-voice")
    if not selected:
        raise DubLocalError("Choose at least one output.")
    if container not in {"mkv", "mp4", "share"}:
        raise DubLocalError("Choose MKV, MP4, or Shareable MP4 output.")
    if burn_subtitles and container != "share":
        raise DubLocalError("Burned subtitles are available only for Shareable MP4.")

    target = normalize_language_code(target_language)
    if target == "auto":
        raise DubLocalError("Choose the output language.")

    wants_media = "media" in selected
    wants_voice = "voice" in selected
    wants_translate = "translate" in selected or wants_voice
    wants_subtitles = bool(selected) or wants_translate or wants_voice or wants_media
    shareable = container == "share"

    magic_flow._notify(progress_callback, 0.01, "Inspecting source")
    info = magic_flow.inspect_magic_source(source_type, youtube_url, local_file)
    decision = magic_flow.recommend_subtitle_source(info, subtitle_policy)
    magic_flow._notify(progress_callback, 0.08, decision.label)

    source_subtitle: Path | None = None
    translated_subtitle: Path | None = None
    voice_wav: Path | None = None
    media_output: Path | None = None
    source_language = "auto"

    if wants_subtitles:
        source_subtitle, source_language = magic_flow._prepare_source_subtitle(
            info,
            decision,
            progress_callback=magic_flow._stage_callback(progress_callback, 0.08, 0.34),
        )
        source_subtitle = Path(export_subtitle(source_subtitle, "srt"))

    if wants_translate and source_language != "auto" and source_language == target:
        wants_translate = False
        magic_flow._notify(progress_callback, 0.36, "Source already matches the requested output language")

    if wants_translate:
        assert source_subtitle is not None
        translated = translate_srt_contextual_with_progress(
            source_subtitle,
            source_language or "auto",
            target,
            progress_callback=magic_flow._stage_callback(progress_callback, 0.34, 0.62),
        )
        source_language = normalize_language_code(translated.source_language)
        translated_subtitle = magic_flow.friendly_subtitle_path(translated.srt_path, info, target)

    if wants_voice:
        timeline = translated_subtitle or source_subtitle
        assert timeline is not None
        voice_language = suggested_voice_language(target if translated_subtitle else source_language)
        if not voice_language:
            raise DubLocalError(
                f"Subtitles are ready, but no prepared local voice engine supports {target}. "
                "Uncheck Voice-over/Media output or choose a supported output language."
            )
        cleaned = prepare_voice_srt(timeline)
        fallback_voice, segment_voices, summary = resolve_auto_voice_plan(
            cleaned,
            info,
            voice_language,
            progress_callback=magic_flow._stage_callback(progress_callback, 0.62, 0.68),
        )
        if single_voice:
            segment_voices = {}
            magic_flow._notify(
                progress_callback,
                0.68,
                f"Single best-match voice selected · {fallback_voice} · {summary}",
            )
        voice = generate_voice_track_with_progress(
            cleaned,
            language=voice_language,
            voice=fallback_voice,
            speed=1.0,
            segment_voices=segment_voices,
            progress_callback=magic_flow._stage_callback(progress_callback, 0.68, 0.82),
        )
        voice_wav = voice.wav_path

    if wants_media:
        intended_subtitle = translated_subtitle or source_subtitle
        intended_language = target if translated_subtitle else source_language

        if wants_voice:
            assert voice_wav is not None
            mode = "replace" if shareable else ("add" if keep_original_audio_track else "replace")
            # Shareable export is encoded once at the delivery stage. The intermediate
            # MKV preserves the selected source stream instead of needlessly encoding it
            # once here and again during H.264 delivery.
            intermediate_format = "mkv" if shareable else container
            rendered = _profiled_render(
                info,
                voice_wav,
                intended_language,
                mode=mode,
                container="mkv" if shareable else container,
                output_format=intermediate_format,
                video_quality=video_quality,
                source_subtitle_path=source_subtitle,
                translated_subtitle_path=translated_subtitle,
                source_language=source_language,
                translated_language=target if translated_subtitle else None,
                mix_strategy="auto",
                progress_callback=magic_flow._stage_callback(
                    progress_callback, 0.82, 0.94 if shareable else 1.0
                ),
            )
            media_output = rendered.output_path
        else:
            assert source_subtitle is not None
            packaged = _profiled_subtitle_package(
                info,
                source_subtitle,
                translated_subtitle,
                source_language,
                target,
                container="mkv" if shareable else container,
                output_format="mkv" if shareable else container,
                video_quality=video_quality,
                progress_callback=magic_flow._stage_callback(
                    progress_callback,
                    0.62 if wants_translate else 0.34,
                    0.90 if shareable else 1.0,
                ),
            )
            media_output = packaged

        if shareable:
            assert media_output is not None
            media_output = _shareable_export(
                media_output,
                info,
                intended_language,
                subtitle_path=intended_subtitle,
                subtitle_language=intended_language,
                video_quality=video_quality,
                burn_subtitles=burn_subtitles,
                progress_callback=magic_flow._stage_callback(
                    progress_callback,
                    0.94 if wants_voice else 0.90,
                    1.0,
                ),
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
    status = " · ".join(outputs) if outputs else "No output files were requested."

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
