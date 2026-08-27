from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np
from platformdirs import user_cache_dir
from yt_dlp import YoutubeDL

from .media import DubLocalError
from .timeline import Segment, parse_srt
from .tts import kokoro_default_voice, kokoro_voice_choices


ProgressCallback = Callable[[float, str], None]
AUTO_VOICE_VALUE = "Auto · match original vocal range"

_ANALYSIS_RATE = 8000
_LOW_CONFIDENT_HZ = 155.0
_HIGH_CONFIDENT_HZ = 185.0
_SPLIT_HZ = 170.0


def auto_voice_choices(language: str | None) -> list[tuple[str, str]]:
    voices = kokoro_voice_choices(language)
    if not voices:
        return []
    return [(AUTO_VOICE_VALUE, AUTO_VOICE_VALUE), *voices]


def auto_default_voice(language: str | None) -> str | None:
    return AUTO_VOICE_VALUE if kokoro_voice_choices(language) else None


def _voice_pair(language: str) -> tuple[str | None, str | None]:
    lower: str | None = None
    higher: str | None = None
    for _label, voice in kokoro_voice_choices(language):
        # Official Kokoro voice IDs encode the supplied voice type in the second
        # character (af/am, bf/bm, ef/em, etc.). This is used only to choose a
        # contrasting TTS preset; it is not a claim about a speaker's identity.
        if len(voice) >= 2 and voice[1] == "m" and lower is None:
            lower = voice
        elif len(voice) >= 2 and voice[1] == "f" and higher is None:
            higher = voice
    return lower, higher


def estimate_fundamental_hz(samples: np.ndarray, sample_rate: int = _ANALYSIS_RATE) -> float | None:
    """Estimate a robust median vocal fundamental for one subtitle-sized sample.

    The estimator is deliberately lightweight: FFT autocorrelation over short frames,
    restricted to a speech/singing F0 range. It is only a practical preset selector,
    not speaker identification or biometric classification.
    """

    values = np.asarray(samples, dtype=np.float32).reshape(-1)
    if values.size < int(sample_rate * 0.12):
        return None
    if np.max(np.abs(values)) > 1.5:
        values = values / 32768.0

    frame_size = int(sample_rate * 0.08)
    hop = int(sample_rate * 0.04)
    min_lag = max(1, int(sample_rate / 320.0))
    max_lag = min(frame_size - 2, int(sample_rate / 70.0))
    nfft = 1
    while nfft < frame_size * 2:
        nfft *= 2

    estimates: list[float] = []
    for start in range(0, max(1, values.size - frame_size + 1), hop):
        frame = values[start : start + frame_size]
        if frame.size < frame_size:
            break
        frame = frame - float(np.mean(frame))
        rms = float(np.sqrt(np.mean(frame * frame)))
        if rms < 0.008:
            continue
        frame = frame * np.hanning(frame_size).astype(np.float32)
        spectrum = np.fft.rfft(frame, n=nfft)
        corr = np.fft.irfft(spectrum * np.conj(spectrum), n=nfft)[:frame_size]
        base = float(corr[0])
        if base <= 1e-9:
            continue
        region = corr[min_lag : max_lag + 1]
        if region.size == 0:
            continue
        local = int(np.argmax(region))
        lag = min_lag + local
        confidence = float(corr[lag] / base)
        if confidence < 0.24:
            continue
        estimates.append(float(sample_rate / lag))

    if not estimates:
        return None
    return float(np.median(np.asarray(estimates, dtype=np.float32)))


def vocal_range_label(fundamental_hz: float | None) -> str | None:
    if fundamental_hz is None:
        return None
    if fundamental_hz <= _LOW_CONFIDENT_HZ:
        return "lower"
    if fundamental_hz >= _HIGH_CONFIDENT_HZ:
        return "higher"
    return "lower" if fundamental_hz < _SPLIT_HZ else "higher"


def _notify(callback: ProgressCallback | None, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), label)


def _new_job_dir() -> Path:
    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="voice-match-", dir=root))


def _require(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise DubLocalError(f"{name} is required for automatic original-voice matching.")
    return path


def _youtube_audio(info: dict[str, Any], output_dir: Path) -> Path:
    url = str(info.get("url") or "").strip()
    if not url:
        raise DubLocalError("The loaded YouTube source no longer has a usable URL for voice matching.")
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "voice-source.%(ext)s"),
        "retries": 3,
        "fragment_retries": 3,
    }
    try:
        with YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        raise DubLocalError(f"Could not fetch source audio for automatic voice matching: {exc}") from exc
    candidates = [item for item in output_dir.glob("voice-source.*") if item.is_file()]
    if not candidates:
        raise DubLocalError("Automatic voice matching could not obtain source audio.")
    candidates.sort(key=lambda item: item.stat().st_size, reverse=True)
    return candidates[0]


def _source_media(info: dict[str, Any], output_dir: Path) -> Path:
    if info.get("kind") == "local":
        path = Path(str(info.get("path") or "")).expanduser().resolve()
        if not path.is_file():
            raise DubLocalError("The selected local source is no longer available for voice matching.")
        return path
    if info.get("kind") == "youtube":
        return _youtube_audio(info, output_dir)
    raise DubLocalError("Load the source before using automatic original-voice matching.")


def _analysis_pcm(info: dict[str, Any], output_dir: Path) -> Path:
    source = _source_media(info, output_dir)
    ffmpeg = _require("ffmpeg")
    output = output_dir / "voice-analysis.s16le"
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
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        str(_ANALYSIS_RATE),
        "-af",
        "highpass=f=70,lowpass=f=350",
        "-f",
        "s16le",
        str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DubLocalError(f"Could not prepare source audio for automatic voice matching: {detail}") from exc
    if not output.is_file() or output.stat().st_size < 2:
        raise DubLocalError("Automatic voice matching produced no usable source-audio analysis data.")
    return output


def _segment_f0(pcm: np.memmap, segment: Segment) -> float | None:
    start = max(0, int(round(segment.start_ms * _ANALYSIS_RATE / 1000)))
    end = min(pcm.size, int(round(segment.end_ms * _ANALYSIS_RATE / 1000)))
    if end - start < int(_ANALYSIS_RATE * 0.12):
        return None
    maximum = int(_ANALYSIS_RATE * 6.0)
    if end - start > maximum:
        midpoint = (start + end) // 2
        start = max(0, midpoint - maximum // 2)
        end = min(pcm.size, start + maximum)
    values = np.asarray(pcm[start:end], dtype=np.float32) / 32768.0
    return estimate_fundamental_hz(values, _ANALYSIS_RATE)


def _smooth_labels(labels: list[str | None]) -> list[str | None]:
    output = list(labels)
    for index in range(1, len(labels) - 1):
        if labels[index - 1] and labels[index + 1] and labels[index - 1] == labels[index + 1]:
            if labels[index] != labels[index - 1]:
                output[index] = labels[index - 1]
    previous: str | None = None
    for index, value in enumerate(output):
        if value is None and previous is not None:
            output[index] = previous
        elif value is not None:
            previous = value
    next_value: str | None = None
    for index in range(len(output) - 1, -1, -1):
        if output[index] is None and next_value is not None:
            output[index] = next_value
        elif output[index] is not None:
            next_value = output[index]
    return output


def resolve_auto_voice_plan(
    subtitle_path: str | Path,
    source_info: dict[str, Any] | None,
    language: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[str, dict[int, str], str]:
    """Return fallback voice, per-segment voice plan and a short human summary."""

    default = kokoro_default_voice(language)
    if not default:
        raise DubLocalError("No Kokoro voice is available for the selected voice language.")
    lower_voice, higher_voice = _voice_pair(language)
    if not lower_voice or not higher_voice:
        return default, {}, "single available voice"
    if not source_info:
        return default, {}, "source audio unavailable · default voice"

    source = Path(subtitle_path).expanduser().resolve()
    try:
        timeline = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        raise DubLocalError(f"Could not read subtitle timing for automatic voice matching: {exc}") from exc
    if not timeline:
        return default, {}, "empty timeline · default voice"

    job_dir = _new_job_dir()
    _notify(progress_callback, 0.05, "Preparing source audio for voice matching")
    pcm_path = _analysis_pcm(dict(source_info), job_dir)
    pcm = np.memmap(pcm_path, dtype="<i2", mode="r")
    labels: list[str | None] = []
    for position, segment in enumerate(timeline):
        labels.append(vocal_range_label(_segment_f0(pcm, segment)))
        _notify(
            progress_callback,
            0.12 + (position + 1) / max(1, len(timeline)) * 0.82,
            f"Matching original vocal range {position + 1}/{len(timeline)}",
        )
    labels = _smooth_labels(labels)

    plan: dict[int, str] = {}
    lower_count = 0
    higher_count = 0
    for segment, label in zip(timeline, labels):
        if label == "lower":
            plan[segment.index] = lower_voice
            lower_count += 1
        elif label == "higher":
            plan[segment.index] = higher_voice
            higher_count += 1
        else:
            plan[segment.index] = default

    fallback = lower_voice if lower_count >= higher_count else higher_voice
    if lower_count and higher_count:
        summary = f"mixed vocal ranges · {lower_voice} + {higher_voice}"
    elif lower_count:
        summary = f"lower vocal range · {lower_voice}"
    elif higher_count:
        summary = f"higher vocal range · {higher_voice}"
    else:
        summary = f"range unclear · {default}"
    _notify(progress_callback, 1.0, "Original vocal-range matching ready")
    return fallback, plan, summary
