from __future__ import annotations

from pathlib import Path

from . import transcription_guard as guard
from . import transcription_v053 as legacy
from .timeline import parse_srt, segments_to_srt


def apply_smart_recovery(result):
    """Apply the established bounded two-pass recovery to an existing transcription.

    This is deliberately an ordinary function in the transcription pipeline. It does
    not replace ``transcribe_source`` or any whisper runner at import time.
    """

    srt_path = Path(result.srt_path)
    wav = srt_path.parent / "speech-16k-mono.wav"
    if not srt_path.is_file() or not wav.is_file():
        return result

    try:
        segments = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return result
    if len(segments) < 2:
        return result

    max_regions, max_total_ms = legacy._recovery_budget()
    candidates = legacy._candidate_regions(segments, result.model_id)
    accepted = []
    attempted = 0
    used_ms = 0

    for region in candidates:
        if attempted >= max_regions or used_ms + region.duration_ms > max_total_ms:
            break
        attempted += 1
        used_ms += region.duration_ms
        recovered = legacy._verified_recovery(result, wav, region, attempted)
        if recovered:
            accepted.append((region, recovered))

    if not accepted:
        return result

    cleaned = legacy._apply_recoveries(segments, accepted)
    try:
        srt_path.write_text(segments_to_srt(cleaned), encoding="utf-8")
    except OSError:
        return result

    existing = guard.quality_note_for(srt_path)
    addition = (
        f"Smart recovery: restored {len(accepted)} low-confidence/missing region(s) "
        f"after two isolated passes agreed; checked {attempted} region(s)."
    )
    guard._remember_quality_note(srt_path, f"{existing} {addition}".strip())
    return type(result)(
        srt_path=srt_path,
        segments=cleaned,
        model_id=result.model_id,
        language=result.language,
        vad_used=result.vad_used,
    )
