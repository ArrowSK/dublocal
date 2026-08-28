from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from . import m5, progress_operations, tts
from .media import DubLocalError
from .timeline import parse_srt


# Keep the existing public TTS API. Only the worker request is enriched with the
# subtitle duration targets, so Kokoro changes its speaking rate during synthesis.
_ORIGINAL_GENERATE = tts.generate_voice_track
_ORIGINAL_RUN_WORKER = tts._run_worker
_PATCH_LOCK = threading.RLock()
_INSTALLED = False


def _target_duration_map(subtitle_path: str | Path) -> dict[int, int]:
    path = Path(subtitle_path).expanduser().resolve()
    if not path.is_file():
        raise DubLocalError("Choose an extracted, transcribed or translated SRT first.")
    try:
        segments = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not parse the subtitle timeline: {exc}") from exc
    return {
        segment.index: max(1, int(segment.end_ms) - int(segment.start_ms))
        for segment in segments
    }


def _apply_timing_targets(
    request: dict[str, Any],
    targets: dict[int, int],
) -> dict[str, Any]:
    """Return a worker request that asks Kokoro to fit each line natively."""

    enriched = dict(request)
    enriched["adaptive_timing"] = True
    enriched_segments: list[dict[str, Any]] = []
    for raw in request.get("segments", []):
        item = dict(raw)
        try:
            index = int(item["index"])
        except (KeyError, TypeError, ValueError):
            enriched_segments.append(item)
            continue
        target = targets.get(index)
        if target is not None:
            item["target_duration_ms"] = int(target)
        enriched_segments.append(item)
    enriched["segments"] = enriched_segments
    return enriched


def _annotate_manifest(
    manifest_path: Path,
    worker_response: dict[str, Any] | None,
) -> None:
    if not manifest_path.is_file() or not worker_response:
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return

    response_segments = {
        int(item["index"]): item
        for item in worker_response.get("segments", [])
        if isinstance(item, dict) and "index" in item
    }
    payload["timing_mode"] = "native_kokoro_speed"
    payload["adaptive_timing"] = True
    payload["post_stretch"] = False

    for item in payload.get("segments", []):
        if not isinstance(item, dict) or "index" not in item:
            continue
        response = response_segments.get(int(item["index"]))
        if not response:
            continue
        item["native_speed"] = float(response.get("speed", payload.get("speed", 1.0)))
        item["pilot_duration_ms"] = int(response.get("pilot_duration_ms") or 0)
        item["target_duration_ms"] = int(response.get("target_duration_ms") or item.get("slot_ms") or 0)
        item["timing_error_ms"] = int(response.get("timing_error_ms") or 0)
        item["generation_passes"] = int(response.get("generation_passes") or 1)

    try:
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return


def generate_voice_track_native_timed(
    subtitle_path: str | Path,
    *,
    language: str,
    voice: str,
    speed: float = 1.0,
    segment_voices: dict[int, str] | None = None,
):
    """Generate each subtitle line at a Kokoro-native speed matched to its timecode.

    Kokoro first renders a normal pilot line, measures that real voice/translation, and
    regenerates only lines that materially miss their subtitle window. This avoids the
    robotic cadence produced by large FFmpeg atempo changes after synthesis.
    """

    targets = _target_duration_map(subtitle_path)
    captured: dict[str, Any] = {}

    def timed_worker(request: dict[str, Any], job_dir: Path):
        enriched = _apply_timing_targets(request, targets)
        response = _ORIGINAL_RUN_WORKER(enriched, job_dir)
        if isinstance(response, dict):
            captured["response"] = response
        return response

    # tts.generate_voice_track resolves _run_worker from its module at runtime. Keep
    # the monkey-patch tightly scoped and locked; DubLocal's UI queue is single-job,
    # but the lock also protects direct/library callers.
    with _PATCH_LOCK:
        previous_worker = tts._run_worker
        tts._run_worker = timed_worker
        try:
            result = _ORIGINAL_GENERATE(
                subtitle_path,
                language=language,
                voice=voice,
                speed=float(speed),
                segment_voices=segment_voices,
            )
        finally:
            tts._run_worker = previous_worker

    _annotate_manifest(result.manifest_path, captured.get("response"))
    return result


def use_native_generated_timing(
    voice_wav: str | Path,
    output_dir: Path,
    *,
    maximum_speedup: float = 1.25,
    progress_callback=None,
) -> m5.TimingFit:
    """Use the Kokoro-timed track directly; do not stretch its waveform at export."""

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
            target_ms = max(1, int(item.get("target_duration_ms") or item.get("slot_ms") or 1))
            error_ms = abs(int(item.get("timing_error_ms") or 0))
            tolerance_ms = max(120, int(round(target_ms * 0.07)))
            if passes > 1:
                adjusted += 1
            if error_ms > tolerance_ms:
                remaining += 1
            if speed > 1.0:
                highest_speedup = max(highest_speedup, speed)

    if progress_callback:
        progress_callback(0.35, "Using native Kokoro timing · no waveform stretching")
    return m5.TimingFit(source, adjusted, remaining, highest_speedup)


def install_native_timing_refinement() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    tts.generate_voice_track = generate_voice_track_native_timed
    # generate_voice_track_with_progress looks up this module global at run time.
    progress_operations.generate_voice_track = generate_voice_track_native_timed
    m5.fit_voice_timing = use_native_generated_timing
    _INSTALLED = True
