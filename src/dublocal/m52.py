from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import m5
from .media import DubLocalError


# A small onset cushion prevents synthetic speech from sounding as if it jumps in
# fractionally before the original line. The rest of the subtitle window is used as
# the target spoken duration.
_MIN_ONSET_MS = 35
_MAX_ONSET_MS = 100
_ONSET_RATIO = 0.025
_MIN_TEMPO = 0.50
_MAX_TEMPO = 2.00
_EXACT_TOLERANCE_MS = 45


@dataclass(frozen=True, slots=True)
class SegmentTimingPlan:
    start_ms: int
    target_duration_ms: int
    tempo_factor: float
    expected_duration_ms: int
    exact: bool


def plan_segment_timing(start_ms: int, end_ms: int, voice_duration_ms: int) -> SegmentTimingPlan:
    """Fit one TTS line to its subtitle timecode while keeping a small onset cushion.

    FFmpeg atempo is intentionally constrained to its natural 0.5–2.0 single-stage
    range. More extreme stretching would technically fill the slot but normally sounds
    worse than leaving some residual silence/overflow, so those cases are reported.
    """

    slot_ms = max(1, int(end_ms) - int(start_ms))
    onset_ms = min(_MAX_ONSET_MS, max(_MIN_ONSET_MS, int(round(slot_ms * _ONSET_RATIO))))
    if onset_ms >= slot_ms:
        onset_ms = max(0, slot_ms // 10)
    target_ms = max(1, slot_ms - onset_ms)
    duration_ms = max(1, int(voice_duration_ms))
    requested = duration_ms / target_ms
    factor = min(_MAX_TEMPO, max(_MIN_TEMPO, requested))
    expected = max(1, int(round(duration_ms / factor)))
    exact = abs(expected - target_ms) <= _EXACT_TOLERANCE_MS
    return SegmentTimingPlan(
        start_ms=int(start_ms) + onset_ms,
        target_duration_ms=target_ms,
        tempo_factor=factor,
        expected_duration_ms=expected,
        exact=exact,
    )


def fit_voice_timing_exact(
    voice_wav: str | Path,
    output_dir: Path,
    *,
    maximum_speedup: float = 1.25,
    progress_callback=None,
) -> m5.TimingFit:
    """Fit each generated voice segment to its own subtitle window.

    v0.5 used a fixed Kokoro speed and only accelerated lines that overflowed. This
    refinement also slows short lines when practical, so translated speech occupies
    approximately the same spoken window as the source. Start times are shifted by a
    tiny onset cushion rather than being advanced before the subtitle timestamp.
    """

    del maximum_speedup  # retained in the signature for the existing M5 caller
    source = Path(voice_wav).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("Generate a voice track before export.")
    manifest = source.parent / "voice-manifest.json"
    if not manifest.is_file():
        m5._notify(progress_callback, 0.32, "Using existing synchronized voice track")
        return m5.TimingFit(source, 0, 0, 1.0)

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        segments = list(payload.get("segments") or [])
        sample_rate = int(payload.get("sample_rate") or 24000)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
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
        duration_ms = int(item.get("voice_duration_ms") or m5._wav_duration_ms(wav))
        plan = plan_segment_timing(start_ms, end_ms, duration_ms)

        fitted_wav = wav
        fitted_duration = duration_ms
        if abs(plan.tempo_factor - 1.0) > 0.005:
            fitted_wav = output_dir / f"fit-{int(item.get('index') or position + 1):04d}.wav"
            m5._tempo_wav(wav, fitted_wav, plan.tempo_factor)
            fitted_duration = m5._wav_duration_ms(fitted_wav)
            adjusted += 1
        if plan.tempo_factor > 1.0:
            highest_speedup = max(highest_speedup, plan.tempo_factor)

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
            f"Matching voice duration to subtitle timing {position + 1}/{len(ordered)}",
        )

    output = output_dir / "voice-fitted.wav"
    m5._assemble_fitted_voice(assembled, output, sample_rate)
    return m5.TimingFit(output, adjusted, remaining, highest_speedup)


def install_runtime_refinements() -> None:
    """Install the v0.5.2 timing fitter without changing the stable M5 public API."""

    m5.fit_voice_timing = fit_voice_timing_exact
