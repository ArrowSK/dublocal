from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import m5, m51
from .language_utils import normalize_language_code
from .media import DubLocalError
from .output_naming import safe_language_suffix, safe_media_stem
from .timeline import parse_srt
from .voice_text import spoken_text


# Legacy M5.3 post-generation timing helpers remain below for compatibility/history,
# but are no longer installed at runtime. Current timing is performed natively by
# Kokoro during synthesis (see native_tts_timing.py), avoiding robotic atempo stretch.
_MIN_TEMPO = 0.30
_MAX_TEMPO = 2.50
_EXACT_TOLERANCE_MS = 25
_MIN_ONSET_MS = 35
_MAX_ONSET_MS = 90
_ONSET_RATIO = 0.018

# Consumer sources can have much higher programme loudness than generated speech. Keep a
# stable original bed at all times, then suppress it further only during dialogue windows.
_ORIGINAL_BED_GAIN = 0.62
_VOICE_GAIN = 1.00


@dataclass(frozen=True, slots=True)
class SegmentTimingPlan:
    start_ms: int
    target_duration_ms: int
    tempo_factor: float
    expected_duration_ms: int
    exact: bool


@dataclass(frozen=True, slots=True)
class SubtitlePackageResult:
    output_path: Path
    source_path: Path
    container: str
    video_quality: str
    video_stream_copy: bool
    embedded_subtitle_tracks: int


def plan_segment_timing(start_ms: int, end_ms: int, voice_duration_ms: int) -> SegmentTimingPlan:
    """Legacy post-generation timing planner retained for compatibility/tests."""

    slot_ms = max(1, int(end_ms) - int(start_ms))
    onset_ms = min(_MAX_ONSET_MS, max(_MIN_ONSET_MS, int(round(slot_ms * _ONSET_RATIO))))
    if onset_ms >= slot_ms:
        onset_ms = max(0, slot_ms // 12)
    target_ms = max(1, slot_ms - onset_ms)
    duration_ms = max(1, int(voice_duration_ms))
    requested = duration_ms / target_ms
    factor = min(_MAX_TEMPO, max(_MIN_TEMPO, requested))
    expected = max(1, int(round(duration_ms / factor)))
    return SegmentTimingPlan(
        start_ms=int(start_ms) + onset_ms,
        target_duration_ms=target_ms,
        tempo_factor=factor,
        expected_duration_ms=expected,
        exact=abs(expected - target_ms) <= _EXACT_TOLERANCE_MS,
    )


def _atempo_chain(factor: float) -> str:
    """Legacy helper: build an atempo chain for archived/compatibility callers."""

    value = float(factor)
    if value <= 0:
        raise DubLocalError("Voice timing requested an invalid tempo factor.")
    stages: list[float] = []
    while value < 0.5 - 1e-9:
        stages.append(0.5)
        value /= 0.5
    while value > 2.0 + 1e-9:
        stages.append(2.0)
        value /= 2.0
    stages.append(value)
    return ",".join(f"atempo={stage:.8f}" for stage in stages)


def _tempo_wav(source: Path, destination: Path, factor: float) -> None:
    ffmpeg = m5._require("ffmpeg")
    try:
        subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-filter:a",
                _atempo_chain(factor),
                "-c:a",
                "pcm_s16le",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DubLocalError(f"FFmpeg could not time-fit a voice segment: {detail}") from exc


def fit_voice_timing_exact(
    voice_wav: str | Path,
    output_dir: Path,
    *,
    maximum_speedup: float = 1.25,
    progress_callback=None,
) -> m5.TimingFit:
    """Legacy post-generation fitter. Current runtime does not install this function."""

    del maximum_speedup
    source = Path(voice_wav).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("Generate a voice track before export.")
    manifest = source.parent / "voice-manifest.json"
    if not manifest.is_file():
        m5._notify(progress_callback, 0.32, "Using existing synchronized voice track")
        return m5.TimingFit(source, 0, 0, 1.0)

    try:
        import json

        payload = json.loads(manifest.read_text(encoding="utf-8"))
        segments = list(payload.get("segments") or [])
        sample_rate = int(payload.get("sample_rate") or 24000)
    except (OSError, ValueError, TypeError) as exc:
        raise DubLocalError(f"Could not read the Kokoro timing manifest: {exc}") from exc
    if not segments:
        return m5.TimingFit(source, 0, 0, 1.0)

    output_dir.mkdir(parents=True, exist_ok=True)
    assembled: list[dict[str, Any]] = []
    adjusted = 0
    remaining = 0
    highest_speedup = 1.0

    ordered = sorted(segments, key=lambda item: int(item.get("start_ms") or 0))
    for position, item in enumerate(ordered):
        wav = Path(str(item.get("wav") or ""))
        if not wav.is_file():
            raise DubLocalError("A Kokoro voice segment referenced by the manifest is missing.")
        start_ms = int(item.get("start_ms") or 0)
        end_ms = int(item.get("end_ms") or start_ms)
        original_duration = int(item.get("voice_duration_ms") or m5._wav_duration_ms(wav))
        plan = plan_segment_timing(start_ms, end_ms, original_duration)

        fitted_wav = wav
        fitted_duration = original_duration
        factor = plan.tempo_factor
        if abs(factor - 1.0) > 0.004:
            fitted_wav = output_dir / f"fit-{int(item.get('index') or position + 1):04d}.wav"
            _tempo_wav(wav, fitted_wav, factor)
            fitted_duration = m5._wav_duration_ms(fitted_wav)
            adjusted += 1

            error_ms = fitted_duration - plan.target_duration_ms
            if abs(error_ms) > _EXACT_TOLERANCE_MS:
                correction = fitted_duration / max(1, plan.target_duration_ms)
                corrected_factor = min(_MAX_TEMPO, max(_MIN_TEMPO, factor * correction))
                if abs(corrected_factor - factor) > 0.003:
                    corrected = output_dir / f"fit-{int(item.get('index') or position + 1):04d}-2.wav"
                    _tempo_wav(wav, corrected, corrected_factor)
                    fitted_wav = corrected
                    fitted_duration = m5._wav_duration_ms(corrected)
                    factor = corrected_factor

        if factor > 1.0:
            highest_speedup = max(highest_speedup, factor)
        if abs(fitted_duration - plan.target_duration_ms) > _EXACT_TOLERANCE_MS:
            remaining += 1

        assembled.append(
            {
                "start_ms": plan.start_ms,
                "duration_ms": fitted_duration,
                "wav": fitted_wav,
            }
        )
        m5._notify(
            progress_callback,
            0.23 + (position + 1) / len(ordered) * 0.12,
            f"Matching voice duration to source timing {position + 1}/{len(ordered)}",
        )

    output = output_dir / "voice-fitted.wav"
    m5._assemble_fitted_voice(assembled, output, sample_rate)
    return m5.TimingFit(output, adjusted, remaining, highest_speedup)


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
        start = max(0.0, segment.start_ms / 1000.0 - 0.18)
        end = max(start, segment.end_ms / 1000.0 + 0.50)
        raw.append((start, end))
    if not raw:
        return []

    merged: list[tuple[float, float]] = [raw[0]]
    for start, end in raw[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 0.24:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _guide_expression(windows: list[tuple[float, float]]) -> str:
    return "+".join(f"between(t\\,{start:.3f}\\,{end:.3f})" for start, end in windows)


def create_balanced_dubbed_mix(
    source_media: Path,
    fitted_voice: Path,
    output_dir: Path,
    *,
    dialogue_subtitle_path: str | Path | None,
    progress_callback=None,
) -> Path:
    """Create a dialogue-anchored mix with a stable original bed and smooth ducking."""

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
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={_ORIGINAL_BED_GAIN:.3f}[orig];"
            f"aevalsrc=exprs='{guide}':s=48000:d={duration:.3f}[dialogue_guide];"
            "[orig][dialogue_guide]sidechaincompress=threshold=0.045:ratio=18:attack=7:release=420[ducked];"
            "[1:a:0]aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={_VOICE_GAIN:.3f}[voice];"
            "[ducked][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "acompressor=threshold=0.35:ratio=2:attack=20:release=250:makeup=1,"
            "alimiter=limit=0.90[mix]"
        )
    else:
        filter_graph = (
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={_ORIGINAL_BED_GAIN:.3f}[orig];"
            "[1:a:0]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice_sc][voice_mix];"
            "[orig][voice_sc]sidechaincompress=threshold=0.022:ratio=18:attack=7:release=420[ducked];"
            f"[voice_mix]volume={_VOICE_GAIN:.3f}[voice];"
            "[ducked][voice]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "acompressor=threshold=0.35:ratio=2:attack=20:release=250:makeup=1,"
            "alimiter=limit=0.90[mix]"
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
        label="Balancing original soundtrack and dub",
        progress_callback=progress_callback,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("FFmpeg did not create a usable dubbed soundtrack.")
    return output


def _subtitle_language(language: str | None) -> str:
    code = normalize_language_code(language)
    return "und" if code == "auto" else m5._target_language_metadata(code)


def package_subtitled_media(
    info: dict[str, Any],
    source_subtitle_path: str | Path,
    source_language: str | None,
    *,
    container: str = "mkv",
    video_quality: str = "source",
    progress_callback=None,
) -> SubtitlePackageResult:
    """Package original media + source subtitles only; do not add translation or dub audio."""

    if not info:
        raise DubLocalError("Load a source before packaging subtitles.")
    if container not in {"mkv", "mp4"}:
        raise DubLocalError("Choose MKV or MP4 output.")
    subtitle = Path(source_subtitle_path).expanduser().resolve()
    if not subtitle.is_file() or subtitle.suffix.lower() != ".srt":
        raise DubLocalError("Extract or transcribe an SRT subtitle track before packaging it with the media.")

    job_dir = m5._new_job_dir("m53-subtitle-package")
    source = m51.acquire_source_media(
        info,
        job_dir,
        video_quality=video_quality,
        progress_callback=progress_callback,
    )
    probe = m5._probe(source)
    duration = m5._duration_seconds(probe)
    video_count = m5._video_stream_count(probe)
    target_height = m51._target_height(video_quality)
    source_height = m51._primary_video_height(probe)
    local_reencode = (
        bool(video_count)
        and info.get("kind") == "local"
        and target_height is not None
        and source_height is not None
        and source_height > target_height
    )

    language = _subtitle_language(source_language)
    output = job_dir / (
        f"{safe_media_stem(info)}.subtitles.{safe_language_suffix(source_language)}.{container}"
    )
    ffmpeg = m5._require("ffmpeg")
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-i",
        str(subtitle),
    ]

    if video_count:
        command += ["-map", "0:v:0?"]
        if local_reencode:
            command += [
                "-vf",
                f"scale=-2:{target_height}",
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                m51._VIDEO_BITRATES[target_height],
                "-pix_fmt",
                "yuv420p",
            ]
        else:
            command += ["-c:v", "copy"]

    command += ["-map", "0:a?", "-c:a", "copy"]
    if container == "mkv":
        command += ["-map", "0:s?", "-c:s", "copy"]
    command += ["-map", "1:0"]
    if container == "mp4":
        command += ["-c:s", "mov_text", "-movflags", "+faststart"]

    preserved = m51._subtitle_stream_count(probe) if container == "mkv" else 0
    command += [
        f"-metadata:s:s:{preserved}",
        f"language={language}",
        f"-metadata:s:s:{preserved}",
        f"title=DubLocal source subtitles · {language}",
        f"-disposition:s:{preserved}",
        "default",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]

    try:
        m5._run_ffmpeg_progress(
            command,
            duration_seconds=duration,
            start_fraction=0.24,
            end_fraction=0.99,
            label=(
                "Encoding selected local video quality and packaging subtitles"
                if local_reencode
                else "Stream-copying original media and packaging subtitles"
            ),
            progress_callback=progress_callback,
        )
    except DubLocalError as exc:
        if container == "mp4":
            raise DubLocalError(
                f"MP4 subtitle packaging was not compatible with this source ({exc}). Choose MKV for the safest no-recode multi-track package."
            ) from exc
        raise

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Subtitle packaging completed without a usable output file.")
    m5._notify(progress_callback, 1.0, "Original media with subtitles ready")
    return SubtitlePackageResult(
        output_path=output,
        source_path=source,
        container=container,
        video_quality=video_quality,
        video_stream_copy=bool(video_count) and not local_reencode,
        embedded_subtitle_tracks=1,
    )


def install_runtime_refinements() -> None:
    """Install M5.3 mix refinements without re-timing generated speech."""

    # Timing is now handled natively during Kokoro generation. Do not install the
    # legacy FFmpeg atempo fitter here; large post-generation stretches sound robotic.
    m51.create_dubbed_mix = create_balanced_dubbed_mix
