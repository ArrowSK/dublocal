from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from platformdirs import user_cache_dir
from yt_dlp import YoutubeDL

from .media import DubLocalError
from .output_naming import dubbed_media_path, safe_language_suffix


ProgressCallback = Callable[[float, str], None]

OUTPUT_MODE_CHOICES = [
    ("Replace primary audio · default", "replace"),
    ("Add dubbed audio as second track", "add"),
]
CONTAINER_CHOICES = [
    ("MKV · recommended · preserves tracks", "mkv"),
    ("MP4 · compatible streams only", "mp4"),
]

_ISO639_2 = {
    "en": "eng",
    "hu": "hun",
    "ru": "rus",
    "de": "deu",
    "fr": "fra",
    "es": "spa",
    "it": "ita",
    "pt": "por",
    "pl": "pol",
    "uk": "ukr",
    "sr": "srp",
    "hr": "hrv",
    "ja": "jpn",
    "zh": "zho",
    "hi": "hin",
}


@dataclass(frozen=True, slots=True)
class TimingFit:
    wav_path: Path
    adjusted_segments: int
    remaining_overflows: int
    maximum_speedup: float


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


def _new_job_dir(prefix: str) -> Path:
    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=root))


def _require(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise DubLocalError(
            f"{name} is required for M5 media export. Open Settings → Local Resources "
            "and repair the installation if the tool is missing."
        )
    return path


def _notify(callback: ProgressCallback | None, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), label)


def _probe(path: Path) -> dict[str, Any]:
    ffprobe = _require("ffprobe")
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
        raise DubLocalError(f"Could not inspect media before M5 export: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def _duration_seconds(probe: dict[str, Any]) -> float:
    try:
        return max(0.0, float((probe.get("format") or {}).get("duration") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _audio_stream_count(probe: dict[str, Any]) -> int:
    return sum(1 for item in probe.get("streams", []) if item.get("codec_type") == "audio")


def _video_stream_count(probe: dict[str, Any]) -> int:
    return sum(1 for item in probe.get("streams", []) if item.get("codec_type") == "video")


def _acquire_youtube_media(
    info: dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback | None,
) -> Path:
    url = str(info.get("url") or "").strip()
    if not url:
        raise DubLocalError("The loaded YouTube source no longer has a usable URL.")

    def hook(payload: dict[str, Any]) -> None:
        if payload.get("status") != "downloading":
            return
        downloaded = float(payload.get("downloaded_bytes") or 0)
        total = float(payload.get("total_bytes") or payload.get("total_bytes_estimate") or 0)
        if total > 0:
            _notify(progress_callback, 0.03 + min(0.18, downloaded / total * 0.18), "Downloading source media")

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestvideo*+bestaudio/best",
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
                "YouTube temporarily rate-limited source-media delivery. Wait and retry, "
                "or use a local media file for M5 export."
            ) from exc
        raise DubLocalError(f"Could not download the YouTube source for M5 export: {message}") from exc

    candidates = [
        path
        for path in output_dir.glob("source.*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise DubLocalError("YouTube download completed without a usable media file.")
    candidates.sort(key=lambda item: item.stat().st_size, reverse=True)
    _notify(progress_callback, 0.22, "Source media ready")
    return candidates[0]


def acquire_source_media(
    info: dict[str, Any],
    output_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    kind = info.get("kind")
    if kind == "local":
        path = Path(str(info.get("path") or "")).expanduser().resolve()
        if not path.is_file():
            raise DubLocalError("The selected local source file no longer exists.")
        _notify(progress_callback, 0.22, "Local source ready")
        return path
    if kind == "youtube":
        _notify(progress_callback, 0.03, "Downloading source media")
        return _acquire_youtube_media(info, output_dir, progress_callback)
    raise DubLocalError("Load a source before rendering dubbed media.")


def _wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
    except wave.Error as exc:
        raise DubLocalError(f"Could not read voice segment {path.name}: {exc}") from exc
    return int(round(frames / max(1, rate) * 1000))


def _tempo_wav(source: Path, destination: Path, factor: float) -> None:
    ffmpeg = _require("ffmpeg")
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
                f"atempo={factor:.6f}",
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
        raise DubLocalError(f"FFmpeg could not fit a voice segment: {detail}") from exc


def _read_pcm_mono(path: Path, expected_rate: int) -> np.ndarray:
    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise DubLocalError(f"Unexpected Kokoro WAV format: {path.name}")
            if handle.getframerate() != expected_rate:
                raise DubLocalError(
                    f"Unexpected voice sample rate {handle.getframerate()} Hz; expected {expected_rate} Hz."
                )
            frames = handle.readframes(handle.getnframes())
    except wave.Error as exc:
        raise DubLocalError(f"Could not read fitted voice segment {path.name}: {exc}") from exc
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def _assemble_fitted_voice(
    entries: list[dict[str, Any]],
    output: Path,
    sample_rate: int,
) -> None:
    if not entries:
        raise DubLocalError("The voice manifest contains no spoken segments.")
    total_ms = max(
        int(item["start_ms"]) + int(item["duration_ms"])
        for item in entries
    )
    total_samples = max(1, int(round(total_ms * sample_rate / 1000)))
    mix = np.zeros(total_samples, dtype=np.float32)
    for item in entries:
        audio = _read_pcm_mono(Path(item["wav"]), sample_rate)
        start = int(round(int(item["start_ms"]) * sample_rate / 1000))
        end = min(total_samples, start + audio.size)
        if end > start:
            mix[start:end] += audio[: end - start]
    with wave.open(str(output), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        pcm = (np.clip(mix, -1.0, 1.0) * 32767.0).astype("<i2")
        handle.writeframes(pcm.tobytes())


def fit_voice_timing(
    voice_wav: str | Path,
    output_dir: Path,
    *,
    maximum_speedup: float = 1.25,
    progress_callback: ProgressCallback | None = None,
) -> TimingFit:
    """Fit overflowing TTS segments by borrowing silence first, then modestly speeding speech.

    M5 never truncates spoken words. If a line still does not fit after the configured
    speed-up ceiling, it is kept intact and reported as a remaining overflow.
    """

    source = Path(voice_wav).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("Generate a voice track before M5 export.")
    manifest = source.parent / "voice-manifest.json"
    if not manifest.is_file():
        _notify(progress_callback, 0.32, "Using existing synchronized voice track")
        return TimingFit(source, 0, 0, 1.0)

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        segments = list(payload.get("segments") or [])
        sample_rate = int(payload.get("sample_rate") or 24000)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise DubLocalError(f"Could not read the Kokoro timing manifest: {exc}") from exc
    if not segments:
        return TimingFit(source, 0, 0, 1.0)

    adjusted = 0
    remaining = 0
    highest_factor = 1.0
    assembled: list[dict[str, Any]] = []
    sorted_segments = sorted(segments, key=lambda item: int(item.get("start_ms") or 0))

    for position, item in enumerate(sorted_segments):
        wav = Path(str(item.get("wav") or ""))
        if not wav.is_file():
            raise DubLocalError("A Kokoro voice segment referenced by the manifest is missing.")
        start_ms = int(item.get("start_ms") or 0)
        end_ms = int(item.get("end_ms") or start_ms)
        duration_ms = int(item.get("voice_duration_ms") or _wav_duration_ms(wav))
        next_start = (
            int(sorted_segments[position + 1].get("start_ms") or end_ms)
            if position + 1 < len(sorted_segments)
            else end_ms
        )
        # Borrow genuine silence up to the next spoken segment before altering speech speed.
        available_ms = max(1, max(end_ms, next_start) - start_ms)
        needed_factor = max(1.0, duration_ms / available_ms)
        factor = min(maximum_speedup, needed_factor)
        highest_factor = max(highest_factor, factor)
        fitted_wav = wav
        fitted_duration = duration_ms
        if factor > 1.015:
            fitted_wav = output_dir / f"fit-{int(item.get('index') or position + 1):04d}.wav"
            _tempo_wav(wav, fitted_wav, factor)
            fitted_duration = _wav_duration_ms(fitted_wav)
            adjusted += 1
        if fitted_duration > available_ms:
            remaining += 1
        assembled.append(
            {
                "start_ms": start_ms,
                "duration_ms": fitted_duration,
                "wav": fitted_wav,
            }
        )
        _notify(
            progress_callback,
            0.23 + (position + 1) / len(sorted_segments) * 0.12,
            f"Fitting voice timing {position + 1}/{len(sorted_segments)}",
        )

    if adjusted == 0:
        return TimingFit(source, 0, remaining, 1.0)

    output = output_dir / "voice-fitted.wav"
    _assemble_fitted_voice(assembled, output, sample_rate)
    return TimingFit(output, adjusted, remaining, highest_factor)


def _run_ffmpeg_progress(
    command: list[str],
    *,
    duration_seconds: float,
    start_fraction: float,
    end_fraction: float,
    label: str,
    progress_callback: ProgressCallback | None,
) -> None:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        if not line.startswith("out_time_ms="):
            continue
        try:
            # ffmpeg -progress reports microseconds despite the historical key name.
            current_seconds = int(line.split("=", 1)[1].strip()) / 1_000_000
        except ValueError:
            continue
        fraction = current_seconds / duration_seconds if duration_seconds > 0 else 0.0
        _notify(
            progress_callback,
            start_fraction + min(1.0, max(0.0, fraction)) * (end_fraction - start_fraction),
            label,
        )
    stderr = process.stderr.read() if process.stderr is not None else ""
    return_code = process.wait()
    if return_code != 0:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else f"exit code {return_code}"
        raise DubLocalError(f"FFmpeg {label.lower()} failed: {detail}")
    _notify(progress_callback, end_fraction, label)


def create_dubbed_mix(
    source_media: Path,
    fitted_voice: Path,
    output_dir: Path,
    *,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Duck the original primary soundtrack under TTS and create one AAC dubbed mix."""

    ffmpeg = _require("ffmpeg")
    probe = _probe(source_media)
    if _audio_stream_count(probe) < 1:
        raise DubLocalError("The source media has no audio track to mix with the DubLocal voice track.")
    duration = _duration_seconds(probe)
    output = output_dir / "dubbed-mix.m4a"
    filter_graph = (
        "[0:a:0]aresample=48000,aformat=channel_layouts=stereo[orig];"
        "[1:a:0]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice_sc][voice_mix];"
        "[orig][voice_sc]sidechaincompress=threshold=0.015:ratio=12:attack=18:release=280[ducked];"
        "[ducked][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
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
    _run_ffmpeg_progress(
        command,
        duration_seconds=duration,
        start_fraction=0.36,
        end_fraction=0.68,
        label="Mixing dubbed soundtrack",
        progress_callback=progress_callback,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("FFmpeg did not create a usable dubbed soundtrack.")
    return output


def _target_language_metadata(language: str) -> str:
    base = safe_language_suffix(language).lower().split("-", 1)[0]
    return _ISO639_2.get(base, base[:3] or "und")


def remux_dubbed_media(
    source_media: Path,
    dubbed_audio: Path,
    info: dict[str, Any],
    language: str,
    *,
    mode: str,
    container: str,
    output_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> RenderResult:
    if mode not in {"replace", "add"}:
        raise DubLocalError("Choose a valid M5 audio-track mode.")
    if container not in {"mkv", "mp4"}:
        raise DubLocalError("Choose MKV or MP4 output.")

    ffmpeg = _require("ffmpeg")
    probe = _probe(source_media)
    audio_count = _audio_stream_count(probe)
    video_count = _video_stream_count(probe)
    duration = _duration_seconds(probe)
    output = dubbed_media_path(output_dir, info, language, container)
    target_lang = _target_language_metadata(language)

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

    if video_count:
        command += ["-map", "0:v?", "-c:v", "copy"]

    if mode == "replace":
        # New mixed DubLocal soundtrack becomes audio stream 0. Preserve any additional
        # source-language/commentary tracks after it, but replace the original primary.
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

    # MKV safely preserves arbitrary subtitle codecs. MP4 intentionally keeps the
    # remux conservative; subtitle files remain separately downloadable from DubLocal.
    if container == "mkv":
        command += ["-map", "0:s?", "-c:s", "copy"]

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

    command += ["-progress", "pipe:1", "-nostats", str(output)]
    try:
        _run_ffmpeg_progress(
            command,
            duration_seconds=duration,
            start_fraction=0.70,
            end_fraction=0.99,
            label="Stream-copying video and remuxing audio",
            progress_callback=progress_callback,
        )
    except DubLocalError as exc:
        if container == "mp4":
            raise DubLocalError(
                f"MP4 stream-copy/remux was not compatible with this source ({exc}). "
                "Choose MKV to preserve the original video without re-encoding. DubLocal does not silently re-encode video."
            ) from exc
        raise

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("M5 remux completed without a usable output file.")

    _notify(progress_callback, 1.0, "Dubbed media ready")
    return RenderResult(
        output_path=output,
        mixed_audio_path=dubbed_audio,
        fitted_voice_path=dubbed_audio,  # replaced by render_dubbed_media below
        source_path=source_media,
        mode=mode,
        container=container,
        language=language,
        video_stream_copy=bool(video_count),
        original_audio_tracks=audio_count,
        output_audio_tracks=output_audio_count,
        timing_adjusted_segments=0,
        remaining_timing_overflows=0,
    )


def render_dubbed_media(
    info: dict[str, Any],
    voice_wav: str | Path,
    language: str,
    *,
    mode: str = "replace",
    container: str = "mkv",
    progress_callback: ProgressCallback | None = None,
) -> RenderResult:
    """Run the complete M5 path: acquire → fit → duck/mix → stream-copy/remux."""

    if not info:
        raise DubLocalError("Load a source before M5 export.")
    if not language:
        raise DubLocalError("Choose/generate a voice language before M5 export.")

    voice = Path(voice_wav).expanduser().resolve()
    if not voice.is_file():
        raise DubLocalError("Generate a voice track before M5 export.")

    job_dir = _new_job_dir("m5-render")
    source = acquire_source_media(info, job_dir, progress_callback)
    timing = fit_voice_timing(
        voice,
        job_dir,
        maximum_speedup=1.25,
        progress_callback=progress_callback,
    )
    mixed = create_dubbed_mix(
        source,
        timing.wav_path,
        job_dir,
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
    )
