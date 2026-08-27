from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Callable

from platformdirs import user_cache_dir

from .transcription import WHISPER_MODELS, install_whisper_model, whisper_model_path
from .tts import VoiceTrackResult, generate_voice_track


ProgressCallback = Callable[[float, str], None]


def _run_in_thread(target):
    box: dict[str, object] = {}

    def runner():
        try:
            box["result"] = target()
        except BaseException as exc:  # re-raised in caller thread
            box["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread, box


def _raise_or_result(box: dict[str, object]):
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box.get("result")


def _mib_from_label(value: str) -> float:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*MiB", value)
    return float(match.group(1)) if match else 0.0


def install_whisper_model_with_progress(
    model_id: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    destination = whisper_model_path(model_id)
    if destination.is_file():
        if progress_callback:
            progress_callback(0.15, "Verifying existing Whisper model")
        result = install_whisper_model(model_id)
        if progress_callback:
            progress_callback(1.0, "Whisper model ready")
        return result

    expected_mib = _mib_from_label(str(WHISPER_MODELS[model_id]["size"]))
    expected_bytes = max(1, int(expected_mib * 1024 * 1024))
    part = destination.with_suffix(".bin.part")
    thread, box = _run_in_thread(lambda: install_whisper_model(model_id))
    if progress_callback:
        progress_callback(0.01, "Starting Whisper model download")
    while thread.is_alive():
        try:
            current = part.stat().st_size if part.exists() else 0
        except OSError:
            current = 0
        fraction = min(0.94, current / expected_bytes) if current else 0.01
        if progress_callback:
            progress_callback(max(0.01, fraction), "Downloading Whisper model")
        time.sleep(0.4)
    thread.join()
    result = _raise_or_result(box)
    if progress_callback:
        progress_callback(0.97, "Verifying Whisper checksum")
        progress_callback(1.0, "Whisper model ready")
    return result  # type: ignore[return-value]


def generate_voice_track_with_progress(
    subtitle_path: str | Path,
    *,
    language: str,
    voice: str,
    speed: float,
    progress_callback: ProgressCallback | None = None,
) -> VoiceTrackResult:
    from .timeline import parse_srt

    source = Path(subtitle_path)
    segments = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    total = max(1, len(segments))
    jobs_root = Path(user_cache_dir("DubLocal")) / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    before = {item for item in jobs_root.glob("kokoro-*") if item.is_dir()}

    thread, box = _run_in_thread(
        lambda: generate_voice_track(
            source,
            language=language,
            voice=voice,
            speed=float(speed),
        )
    )
    job_dir: Path | None = None
    if progress_callback:
        progress_callback(0.02, "Loading Kokoro and voice assets")

    while thread.is_alive():
        if job_dir is None:
            candidates = [
                item
                for item in jobs_root.glob("kokoro-*")
                if item.is_dir() and item not in before
            ]
            if candidates:
                job_dir = max(candidates, key=lambda item: item.stat().st_mtime)
        completed = 0
        if job_dir is not None:
            completed = len(list((job_dir / "segments").glob("segment-*.wav")))
        if progress_callback:
            if completed:
                fraction = min(0.92, 0.05 + 0.85 * completed / total)
                progress_callback(
                    fraction,
                    f"Generating Kokoro speech {min(completed, total)}/{total}",
                )
            else:
                progress_callback(0.03, "Loading Kokoro and voice assets")
        time.sleep(0.5)

    thread.join()
    result = _raise_or_result(box)
    if progress_callback:
        progress_callback(0.96, "Assembling synchronized voice track")
        progress_callback(1.0, "Voice track ready")
    return result  # type: ignore[return-value]
