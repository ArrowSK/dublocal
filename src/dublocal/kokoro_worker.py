from __future__ import annotations

import json
import os
import sys
import wave
from pathlib import Path


_MIN_NATIVE_SPEED = 0.5
_MAX_NATIVE_SPEED = 2.0


def _write_pcm16_wav(path: Path, samples, sample_rate: int) -> int:
    import numpy as np

    array = np.asarray(samples, dtype=np.float32).reshape(-1)
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=-1.0)
    pcm = (np.clip(array, -1.0, 1.0) * 32767.0).astype("<i2", copy=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return int(pcm.size)


def _choose_device(torch) -> str:
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _duration_ms(sample_count: int, sample_rate: int) -> int:
    return int(round(max(0, int(sample_count)) * 1000 / max(1, int(sample_rate))))


def _native_speed_for_target(current_speed: float, measured_ms: int, target_ms: int) -> float:
    """Estimate the Kokoro generation speed needed to fill a subtitle window.

    Kokoro's speed parameter changes prosody during synthesis, which sounds materially
    more natural than stretching an already-generated waveform with FFmpeg atempo.
    """

    speed = max(_MIN_NATIVE_SPEED, min(_MAX_NATIVE_SPEED, float(current_speed)))
    if measured_ms <= 0 or target_ms <= 0:
        return speed
    requested = speed * float(measured_ms) / float(target_ms)
    return max(_MIN_NATIVE_SPEED, min(_MAX_NATIVE_SPEED, requested))


def _timing_tolerance_ms(target_ms: int) -> int:
    # Exact sample-level matching is not useful for natural speech. A small tolerance
    # avoids repeated regeneration for harmless breath/punctuation variation.
    return max(90, int(round(max(1, target_ms) * 0.05)))


def _run(request: dict) -> dict:
    import numpy as np
    import torch
    from kokoro import KPipeline

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    language_code = str(request["lang_code"])
    default_voice = str(request["voice"])
    default_speed = float(request.get("speed", 1.0))
    adaptive_timing = bool(request.get("adaptive_timing", False))
    repo_id = str(request.get("repo_id") or "hexgrad/Kokoro-82M")
    output_dir = Path(request["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    device = str(request.get("device") or "auto")
    if device == "auto":
        device = _choose_device(torch)

    try:
        pipeline = KPipeline(
            lang_code=language_code,
            repo_id=repo_id,
            device=device,
        )
    except Exception:
        if device != "mps":
            raise
        device = "cpu"
        pipeline = KPipeline(
            lang_code=language_code,
            repo_id=repo_id,
            device=device,
        )

    sample_rate = 24000

    def synthesize(text: str, voice: str, speed: float):
        nonlocal pipeline, device
        chunks = []
        try:
            iterator = pipeline(text, voice=voice, speed=speed)
            for _graphemes, _phonemes, audio in iterator:
                part = np.asarray(audio, dtype=np.float32).reshape(-1)
                if part.size:
                    chunks.append(part)
        except Exception:
            if device != "mps":
                raise
            device = "cpu"
            pipeline = KPipeline(
                lang_code=language_code,
                repo_id=repo_id,
                device=device,
            )
            chunks = []
            for _graphemes, _phonemes, audio in pipeline(text, voice=voice, speed=speed):
                part = np.asarray(audio, dtype=np.float32).reshape(-1)
                if part.size:
                    chunks.append(part)
        if not chunks:
            raise RuntimeError("Kokoro returned no audio.")
        return np.concatenate(chunks)

    generated: list[dict] = []
    for item in request.get("segments", []):
        index = int(item["index"])
        text = str(item.get("text") or "").strip()
        voice = str(item.get("voice") or default_voice)
        target_ms = max(0, int(item.get("target_duration_ms") or 0))
        segment_speed = max(
            _MIN_NATIVE_SPEED,
            min(_MAX_NATIVE_SPEED, float(item.get("speed", default_speed))),
        )
        if not text:
            generated.append(
                {
                    "index": index,
                    "voice": voice,
                    "speed": segment_speed,
                    "path": None,
                    "samples": 0,
                    "duration_ms": 0,
                    "target_duration_ms": target_ms,
                    "timing_error_ms": -target_ms if target_ms else 0,
                    "generation_passes": 0,
                }
            )
            continue

        # Pass 1 is a natural Kokoro render. Its measured duration provides a much
        # better speed estimate than characters-per-second heuristics across languages.
        audio = synthesize(text, voice, segment_speed)
        pilot_samples = int(audio.size)
        pilot_duration = _duration_ms(pilot_samples, sample_rate)
        final_speed = segment_speed
        final_duration = pilot_duration
        generation_passes = 1

        if adaptive_timing and target_ms > 0:
            tolerance = _timing_tolerance_ms(target_ms)
            desired_speed = _native_speed_for_target(segment_speed, pilot_duration, target_ms)
            if (
                abs(pilot_duration - target_ms) > tolerance
                and abs(desired_speed - segment_speed) >= 0.025
            ):
                audio = synthesize(text, voice, desired_speed)
                final_speed = desired_speed
                final_duration = _duration_ms(int(audio.size), sample_rate)
                generation_passes = 2

                # Kokoro duration is close to inverse speed but not perfectly linear.
                # One native re-generation correction is enough; never waveform-stretch.
                corrected_speed = _native_speed_for_target(final_speed, final_duration, target_ms)
                if (
                    abs(final_duration - target_ms) > tolerance
                    and abs(corrected_speed - final_speed) >= 0.025
                    and _MIN_NATIVE_SPEED < corrected_speed < _MAX_NATIVE_SPEED
                ):
                    audio = synthesize(text, voice, corrected_speed)
                    final_speed = corrected_speed
                    final_duration = _duration_ms(int(audio.size), sample_rate)
                    generation_passes = 3

        output = output_dir / f"segment-{index:06d}.wav"
        sample_count = _write_pcm16_wav(output, audio, sample_rate)
        final_duration = _duration_ms(sample_count, sample_rate)
        generated.append(
            {
                "index": index,
                "voice": voice,
                "speed": final_speed,
                "path": str(output),
                "samples": sample_count,
                "duration_ms": final_duration,
                "pilot_duration_ms": pilot_duration,
                "target_duration_ms": target_ms,
                "timing_error_ms": final_duration - target_ms if target_ms else 0,
                "generation_passes": generation_passes,
            }
        )

    return {
        "ok": True,
        "device": device,
        "sample_rate": sample_rate,
        "repo_id": repo_id,
        "voice": default_voice,
        "speed": default_speed,
        "adaptive_timing": adaptive_timing,
        "segments": generated,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: kokoro_worker.py REQUEST.json RESPONSE.json", file=sys.stderr)
        return 2

    request_path = Path(sys.argv[1])
    response_path = Path(sys.argv[2])
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = _run(request)
        code = 0
    except Exception as exc:
        response = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 1

    response_path.write_text(
        json.dumps(response, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
