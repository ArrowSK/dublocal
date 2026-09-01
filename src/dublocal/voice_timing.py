from __future__ import annotations

import json
from pathlib import Path

from . import m5
from .media import DubLocalError


def native_voice_timing(
    voice_wav: str | Path,
    output_dir: Path,
    *,
    maximum_speedup: float = 1.25,
    progress_callback=None,
) -> m5.TimingFit:
    """Use provider-native timing directly; never post-stretch a generated voice track.

    Kokoro and Hungarian providers already regenerate materially overflowing lines at
    their native speaking-rate controls. Export therefore only reports timing quality;
    it does not alter the generated waveform or subtitle timestamps.
    """

    del output_dir, maximum_speedup
    source = Path(voice_wav).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("Generate a voice track before export.")

    adjusted = 0
    remaining = 0
    highest_speedup = 1.0
    manifest = source.parent / "voice-manifest.json"
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        for item in payload.get("segments", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            passes = int(item.get("generation_passes") or 1)
            speed = float(item.get("native_speed") or payload.get("speed", 1.0))
            target_ms = max(
                1,
                int(item.get("target_duration_ms") or item.get("slot_ms") or 1),
            )
            overflow_ms = max(0, int(item.get("timing_error_ms") or 0))
            tolerance_ms = max(120, int(round(target_ms * 0.07)))
            if passes > 1:
                adjusted += 1
            if overflow_ms > tolerance_ms:
                remaining += 1
            if speed > 1.0:
                highest_speedup = max(highest_speedup, speed)

    if progress_callback:
        progress_callback(0.35, "Using provider-native timing · no waveform stretching")
    return m5.TimingFit(source, adjusted, remaining, highest_speedup)
