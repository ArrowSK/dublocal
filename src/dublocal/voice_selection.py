from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

from .hungarian_tts import HUNGARIAN_LANGUAGE, is_macos_system_voice
from .media import DubLocalError
from .timeline import parse_srt
from .voice_engine import default_voice, voice_choices
from .voice_match import (
    AUTO_VOICE_VALUE,
    _analysis_pcm,
    _new_job_dir,
    _notify,
    _segment_f0,
    _smooth_labels,
    vocal_range_label,
)


ProgressCallback = Callable[[float, str], None]


def auto_voice_choices(language: str | None) -> list[tuple[str, str]]:
    voices = voice_choices(language)
    if not voices:
        return []
    return [(AUTO_VOICE_VALUE, AUTO_VOICE_VALUE), *voices]


def auto_default_voice(language: str | None) -> str | None:
    return AUTO_VOICE_VALUE if voice_choices(language) else None


def _voice_pair(language: str) -> tuple[str | None, str | None]:
    lower: str | None = None
    higher: str | None = None
    for _label, voice in voice_choices(language):
        # Provider voice ids use the established second-character f/m convention where
        # available (af/am, rf/rm, uf/um). Unknown/custom ids simply do not participate
        # in automatic range pairing and fall back to their configured default.
        if len(voice) >= 2 and voice[1] == "m" and lower is None:
            lower = voice
        elif len(voice) >= 2 and voice[1] == "f" and higher is None:
            higher = voice
    return lower, higher


def resolve_auto_voice_plan(
    subtitle_path: str | Path,
    source_info: dict[str, Any] | None,
    language: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[str, dict[int, str], str]:
    """Resolve the automatic voice plan through the canonical voice catalogue."""

    fallback_default = default_voice(language)
    if not fallback_default:
        raise DubLocalError("No local voice is available for the selected voice language.")

    # macOS Hungarian Auto deliberately uses the installed system voice as one
    # consistent narration voice. Piper remains available explicitly and is the
    # automatic cross-platform route when no macOS hu-HU system voice exists.
    if language == HUNGARIAN_LANGUAGE and is_macos_system_voice(fallback_default):
        return fallback_default, {}, "macOS system Hungarian voice"

    lower_voice, higher_voice = _voice_pair(language)
    if not lower_voice or not higher_voice:
        return fallback_default, {}, "single available voice"
    if not source_info:
        return fallback_default, {}, "source audio unavailable · default voice"

    source = Path(subtitle_path).expanduser().resolve()
    try:
        timeline = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        raise DubLocalError(f"Could not read subtitle timing for automatic voice matching: {exc}") from exc
    if not timeline:
        return fallback_default, {}, "empty timeline · default voice"

    job_dir = _new_job_dir()
    _notify(progress_callback, 0.05, "Preparing source audio for voice matching")
    pcm_path = _analysis_pcm(dict(source_info), job_dir)
    pcm = np.memmap(pcm_path, dtype="<i2", mode="r")
    try:
        labels: list[str | None] = []
        for position, segment in enumerate(timeline):
            labels.append(vocal_range_label(_segment_f0(pcm, segment)))
            _notify(
                progress_callback,
                0.12 + (position + 1) / max(1, len(timeline)) * 0.82,
                f"Matching original vocal range {position + 1}/{len(timeline)}",
            )
        labels = _smooth_labels(labels)
    finally:
        mmap = getattr(pcm, "_mmap", None)
        if mmap is not None:
            mmap.close()
        del pcm

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
            plan[segment.index] = fallback_default

    fallback = lower_voice if lower_count >= higher_count else higher_voice
    if lower_count and higher_count:
        summary = f"mixed vocal ranges · {lower_voice} + {higher_voice}"
    elif lower_count:
        summary = f"lower vocal range · {lower_voice}"
    elif higher_count:
        summary = f"higher vocal range · {higher_voice}"
    else:
        summary = f"range unclear · {fallback_default}"
    _notify(progress_callback, 1.0, "Original vocal-range matching ready")
    return fallback, plan, summary
