from __future__ import annotations

import json
import os
import sys
import wave
from pathlib import Path


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


def _run(request: dict) -> dict:
    import numpy as np
    import torch
    from kokoro import KPipeline

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    language_code = str(request["lang_code"])
    voice = str(request["voice"])
    speed = float(request.get("speed", 1.0))
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
        # Some Kokoro/PyTorch combinations can expose an MPS device but fail
        # while constructing the pipeline. CPU is slower but is the safe local
        # fallback and keeps the source application's environment untouched.
        if device != "mps":
            raise
        device = "cpu"
        pipeline = KPipeline(
            lang_code=language_code,
            repo_id=repo_id,
            device=device,
        )

    sample_rate = 24000
    generated: list[dict] = []
    for item in request.get("segments", []):
        index = int(item["index"])
        text = str(item.get("text") or "").strip()
        if not text:
            generated.append(
                {
                    "index": index,
                    "path": None,
                    "samples": 0,
                    "duration_ms": 0,
                }
            )
            continue

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
            # Retry the segment on CPU if a later MPS operation is unsupported.
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
            raise RuntimeError(f"Kokoro returned no audio for subtitle segment {index}.")

        audio = np.concatenate(chunks)
        output = output_dir / f"segment-{index:06d}.wav"
        sample_count = _write_pcm16_wav(output, audio, sample_rate)
        generated.append(
            {
                "index": index,
                "path": str(output),
                "samples": sample_count,
                "duration_ms": int(round(sample_count * 1000 / sample_rate)),
            }
        )

    return {
        "ok": True,
        "device": device,
        "sample_rate": sample_rate,
        "repo_id": repo_id,
        "voice": voice,
        "speed": speed,
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
    except Exception as exc:  # worker boundary: serialize the failure to DubLocal
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
