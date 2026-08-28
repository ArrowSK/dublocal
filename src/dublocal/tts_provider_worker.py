from __future__ import annotations

import json
import os
import sys
import wave
from pathlib import Path


_MIN_SPEED = 0.5
_MAX_SPEED = 2.0
_SAMPLE_RATE = 24000


def _duration_ms(sample_count: int) -> int:
    return int(round(max(0, int(sample_count)) * 1000 / _SAMPLE_RATE))


def _fit_speed(current_speed: float, measured_ms: int, target_ms: int) -> float:
    """Keep natural pace when a line fits; accelerate only genuine overflow."""

    speed = max(_MIN_SPEED, min(_MAX_SPEED, float(current_speed)))
    if measured_ms <= 0 or target_ms <= 0 or measured_ms <= target_ms:
        return speed
    requested = speed * float(measured_ms) / float(target_ms)
    return max(speed, min(_MAX_SPEED, requested))


def _tolerance_ms(target_ms: int) -> int:
    return max(90, int(round(max(1, target_ms) * 0.05)))


def _write_pcm16(path: Path, samples) -> int:
    import numpy as np

    array = np.asarray(samples, dtype=np.float32).reshape(-1)
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=-1.0)
    pcm = (np.clip(array, -1.0, 1.0) * 32767.0).astype("<i2", copy=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(_SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    return int(pcm.size)


def _voice(manifest: dict, voice_id: str) -> dict:
    for voice in manifest.get("voices", []):
        if str(voice.get("id")) == voice_id:
            return dict(voice)
    raise RuntimeError(f"Voice {voice_id!r} is not declared by this TTS provider.")


def _phoneme_chunks(phonemes: str, maximum: int = 500) -> list[str]:
    value = " ".join(str(phonemes).split()).strip()
    if len(value) <= maximum:
        return [value] if value else []
    words = value.split(" ")
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and length + extra > maximum:
            chunks.append(" ".join(current))
            current, length = [], 0
        if len(word) > maximum:
            if current:
                chunks.append(" ".join(current))
                current, length = [], 0
            chunks.extend(word[index : index + maximum] for index in range(0, len(word), maximum))
            continue
        current.append(word)
        length += len(word) + (1 if length else 0)
    if current:
        chunks.append(" ".join(current))
    return [chunk for chunk in chunks if chunk]


def _russian_phonemes(provider_root: Path, manifest: dict, text: str) -> list[str]:
    from russian_frontend import RussianFrontend

    frontend = RussianFrontend(
        provider_root,
        provider_root / str(manifest["config_file"]),
        accent_workdir=provider_root / ".ruaccent",
    )
    phonemes, oov = frontend.phonemize(text)
    if oov:
        visible = " ".join(sorted(oov))
        raise RuntimeError(f"Russian frontend produced unsupported Kokoro symbols: {visible}")
    return _phoneme_chunks(phonemes)


def _official_phonemes(manifest: dict, text: str) -> list[str]:
    from kokoro import KPipeline

    frontend = str(manifest["frontend"])
    lang_code = frontend.rsplit("-", 1)[-1]
    pipeline = KPipeline(lang_code=lang_code, model=False, repo_id="hexgrad/Kokoro-82M")
    chunks: list[str] = []
    for _graphemes, phonemes, _audio in pipeline(text, model=False):
        chunks.extend(_phoneme_chunks(str(phonemes)))
    return chunks


def _prepare_frontend(provider_root: Path, manifest: dict):
    if str(manifest["frontend"]) == "russian-v2":
        # Construct once so RUAccent/model downloads are paid only once per worker.
        from russian_frontend import RussianFrontend

        frontend = RussianFrontend(
            provider_root,
            provider_root / str(manifest["config_file"]),
            accent_workdir=provider_root / ".ruaccent",
        )

        def phonemize(text: str) -> list[str]:
            value, oov = frontend.phonemize(text)
            if oov:
                visible = " ".join(sorted(oov))
                raise RuntimeError(f"Russian frontend produced unsupported Kokoro symbols: {visible}")
            return _phoneme_chunks(value)

        return phonemize

    from kokoro import KPipeline

    lang_code = str(manifest["frontend"]).rsplit("-", 1)[-1]
    pipeline = KPipeline(lang_code=lang_code, model=False, repo_id="hexgrad/Kokoro-82M")

    def phonemize(text: str) -> list[str]:
        chunks: list[str] = []
        for _graphemes, value, _audio in pipeline(text, model=False):
            chunks.extend(_phoneme_chunks(str(value)))
        return chunks

    return phonemize


def _run(request: dict) -> dict:
    import numpy as np
    import torch
    from kokoro import KModel

    manifest = dict(request["provider_manifest"])
    if str(manifest.get("backend")) != "kokoro-local":
        raise RuntimeError("Provider worker accepts only the audited kokoro-local backend.")
    root = Path(str(request["provider_root"])).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError("Prepared TTS provider directory is missing.")

    output_dir = Path(str(request["output_dir"])).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    default_voice = str(request["voice"])
    default_speed = float(request.get("speed", 1.0))
    adaptive_timing = bool(request.get("adaptive_timing", False))

    # CPU is the compatibility baseline for third-party providers. It works across
    # all Apple Silicon generations and avoids depending on model-specific MPS ops.
    device = str(request.get("device") or "cpu")
    if device not in {"cpu", "mps", "cuda"}:
        device = "cpu"
    mps = getattr(torch.backends, "mps", None)
    if device == "mps" and (mps is None or not mps.is_available()):
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    model_cache: dict[str, object] = {}
    voice_cache: dict[str, object] = {}
    phonemize = _prepare_frontend(root, manifest)

    def model_for(voice_id: str):
        voice = _voice(manifest, voice_id)
        relative = str(voice["model_file"])
        if relative not in model_cache:
            model_cache[relative] = KModel(
                repo_id="dublocal/local-provider",
                config=str(root / str(manifest["config_file"])),
                model=str(root / relative),
            ).to(device).eval()
        return model_cache[relative]

    def pack_for(voice_id: str):
        voice = _voice(manifest, voice_id)
        relative = str(voice["voice_file"])
        if relative not in voice_cache:
            voice_cache[relative] = torch.load(
                str(root / relative), map_location="cpu", weights_only=True
            )
        return voice_cache[relative]

    def synthesize(text: str, voice_id: str, speed: float):
        chunks = phonemize(text)
        if not chunks:
            raise RuntimeError("TTS frontend returned no pronounceable text.")
        model = model_for(voice_id)
        pack = pack_for(voice_id).to(model.device)
        parts = []
        for phonemes in chunks:
            reference_index = min(max(0, len(phonemes) - 1), max(0, int(pack.shape[0]) - 1))
            audio = model(phonemes, pack[reference_index], speed=float(speed))
            values = np.asarray(audio, dtype=np.float32).reshape(-1)
            if values.size:
                parts.append(values)
        if not parts:
            raise RuntimeError("Kokoro provider returned no audio.")
        return np.concatenate(parts)

    generated: list[dict] = []
    for item in request.get("segments", []):
        index = int(item["index"])
        text = str(item.get("text") or "").strip()
        voice_id = str(item.get("voice") or default_voice)
        target_ms = max(0, int(item.get("target_duration_ms") or 0))
        speed = max(_MIN_SPEED, min(_MAX_SPEED, float(item.get("speed", default_speed))))
        if not text:
            generated.append(
                {
                    "index": index,
                    "voice": voice_id,
                    "speed": speed,
                    "path": None,
                    "samples": 0,
                    "duration_ms": 0,
                    "target_duration_ms": target_ms,
                    "timing_error_ms": -target_ms if target_ms else 0,
                    "generation_passes": 0,
                }
            )
            continue

        audio = synthesize(text, voice_id, speed)
        pilot_ms = _duration_ms(int(audio.size))
        final_speed = speed
        final_ms = pilot_ms
        passes = 1

        if adaptive_timing and target_ms > 0 and pilot_ms > target_ms + _tolerance_ms(target_ms):
            desired = _fit_speed(speed, pilot_ms, target_ms)
            if desired > speed + 0.024:
                audio = synthesize(text, voice_id, desired)
                final_speed = desired
                final_ms = _duration_ms(int(audio.size))
                passes = 2
            if final_ms > target_ms + _tolerance_ms(target_ms):
                corrected = _fit_speed(final_speed, final_ms, target_ms)
                if corrected > final_speed + 0.024 and corrected <= _MAX_SPEED:
                    audio = synthesize(text, voice_id, corrected)
                    final_speed = corrected
                    final_ms = _duration_ms(int(audio.size))
                    passes = 3

        path = output_dir / f"segment-{index:06d}.wav"
        samples = _write_pcm16(path, audio)
        final_ms = _duration_ms(samples)
        generated.append(
            {
                "index": index,
                "voice": voice_id,
                "speed": final_speed,
                "path": str(path),
                "samples": samples,
                "duration_ms": final_ms,
                "pilot_duration_ms": pilot_ms,
                "target_duration_ms": target_ms,
                "timing_error_ms": final_ms - target_ms if target_ms else 0,
                "generation_passes": passes,
            }
        )

    return {
        "ok": True,
        "device": device,
        "sample_rate": _SAMPLE_RATE,
        "provider_id": manifest["id"],
        "voice": default_voice,
        "speed": default_speed,
        "adaptive_timing": adaptive_timing,
        "segments": generated,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: tts_provider_worker.py REQUEST.json RESPONSE.json", file=sys.stderr)
        return 2
    request_path = Path(sys.argv[1])
    response_path = Path(sys.argv[2])
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = _run(request)
        code = 0
    except Exception as exc:
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        code = 1
    response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
