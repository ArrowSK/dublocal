from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from platformdirs import user_cache_dir

from .dependencies import discover_python_runtime, shared_huggingface_cache
from .media import DubLocalError
from .timeline import Segment, parse_srt


KOKORO_OFFICIAL_MODEL_REPO = "hexgrad/Kokoro-82M"
KOKORO_RUNTIME_MODULES = ("kokoro", "numpy", "torch", "huggingface_hub")

KOKORO_LANGUAGES: dict[str, dict[str, Any]] = {
    "en-US": {
        "label": "English · American",
        "lang_code": "a",
        "default_voice": "af_heart",
        "voices": [
            ("Heart · female", "af_heart"),
            ("Bella · female", "af_bella"),
            ("Nicole · female", "af_nicole"),
            ("Aoede · female", "af_aoede"),
            ("Kore · female", "af_kore"),
            ("Sarah · female", "af_sarah"),
            ("Alloy · female", "af_alloy"),
            ("Nova · female", "af_nova"),
            ("Sky · female", "af_sky"),
            ("Jessica · female", "af_jessica"),
            ("River · female", "af_river"),
            ("Fenrir · male", "am_fenrir"),
            ("Michael · male", "am_michael"),
            ("Puck · male", "am_puck"),
            ("Echo · male", "am_echo"),
            ("Eric · male", "am_eric"),
            ("Liam · male", "am_liam"),
            ("Onyx · male", "am_onyx"),
            ("Santa · male", "am_santa"),
            ("Adam · male", "am_adam"),
        ],
    },
    "en-GB": {
        "label": "English · British",
        "lang_code": "b",
        "default_voice": "bf_emma",
        "voices": [
            ("Emma · female", "bf_emma"),
            ("Isabella · female", "bf_isabella"),
            ("Alice · female", "bf_alice"),
            ("Lily · female", "bf_lily"),
            ("Fable · male", "bm_fable"),
            ("George · male", "bm_george"),
            ("Lewis · male", "bm_lewis"),
            ("Daniel · male", "bm_daniel"),
        ],
    },
    "es": {
        "label": "Spanish",
        "lang_code": "e",
        "default_voice": "ef_dora",
        "voices": [
            ("Dora · female", "ef_dora"),
            ("Alex · male", "em_alex"),
            ("Santa · male", "em_santa"),
        ],
    },
    "fr": {
        "label": "French",
        "lang_code": "f",
        "default_voice": "ff_siwis",
        "voices": [("Siwis · female", "ff_siwis")],
    },
    "it": {
        "label": "Italian",
        "lang_code": "i",
        "default_voice": "if_sara",
        "voices": [
            ("Sara · female", "if_sara"),
            ("Nicola · male", "im_nicola"),
        ],
    },
    "pt-BR": {
        "label": "Portuguese · Brazil",
        "lang_code": "p",
        "default_voice": "pf_dora",
        "voices": [
            ("Dora · female", "pf_dora"),
            ("Alex · male", "pm_alex"),
            ("Santa · male", "pm_santa"),
        ],
    },
    "hi": {
        "label": "Hindi",
        "lang_code": "h",
        "default_voice": "hf_alpha",
        "voices": [
            ("Alpha · female", "hf_alpha"),
            ("Beta · female", "hf_beta"),
            ("Omega · male", "hm_omega"),
            ("Psi · male", "hm_psi"),
        ],
    },
    "ja": {
        "label": "Japanese",
        "lang_code": "j",
        "default_voice": "jf_alpha",
        "voices": [
            ("Alpha · female", "jf_alpha"),
            ("Gongitsune · female", "jf_gongitsune"),
            ("Tebukuro · female", "jf_tebukuro"),
            ("Nezumi · female", "jf_nezumi"),
            ("Kumo · male", "jm_kumo"),
        ],
    },
    "zh": {
        "label": "Mandarin Chinese",
        "lang_code": "z",
        "default_voice": "zf_xiaobei",
        "voices": [
            ("Xiaobei · female", "zf_xiaobei"),
            ("Xiaoni · female", "zf_xiaoni"),
            ("Xiaoxiao · female", "zf_xiaoxiao"),
            ("Xiaoyi · female", "zf_xiaoyi"),
            ("Yunjian · male", "zm_yunjian"),
            ("Yunxi · male", "zm_yunxi"),
            ("Yunxia · male", "zm_yunxia"),
            ("Yunyang · male", "zm_yunyang"),
        ],
    },
}

KOKORO_LANGUAGE_CHOICES = [
    (metadata["label"], code) for code, metadata in KOKORO_LANGUAGES.items()
]

_PREPARE_TEXT = {
    "en-US": "Ready.",
    "en-GB": "Ready.",
    "es": "Listo.",
    "fr": "Prêt.",
    "it": "Pronto.",
    "pt-BR": "Pronto.",
    "hi": "तैयार।",
    "ja": "準備完了。",
    "zh": "准备好了。",
}

_TRANSLATION_TO_KOKORO = {
    "en": "en-US",
    "es": "es",
    "fr": "fr",
    "it": "it",
    "pt": "pt-BR",
}


@dataclass(frozen=True, slots=True)
class VoiceSegmentResult:
    index: int
    start_ms: int
    end_ms: int
    text: str
    voice_duration_ms: int
    slot_ms: int
    overflow_ms: int
    wav_path: Path


@dataclass(frozen=True, slots=True)
class VoiceTrackResult:
    wav_path: Path
    manifest_path: Path
    segments: list[VoiceSegmentResult]
    language: str
    voice: str
    speed: float
    device: str
    runtime_label: str


def _repository_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if not (root / "pyproject.toml").is_file():
        raise DubLocalError("DubLocal could not locate its installation folder.")
    return root


def _new_job_dir(prefix: str) -> Path:
    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=root))


def kokoro_runtime():
    return discover_python_runtime(KOKORO_RUNTIME_MODULES, allow_current=True)


def kokoro_runtime_status() -> str:
    runtime = kokoro_runtime()
    cache = shared_huggingface_cache()
    if runtime is None:
        runtime_line = "[runtime] not ready · Prepare Kokoro will reuse a compatible local environment or install one for DubLocal"
    else:
        runtime_line = f"[runtime] ready · {runtime.label} · {runtime.python}"
    return (
        "```text\n"
        "[engine] Kokoro · local TTS\n"
        f"{runtime_line}\n"
        f"[model] {KOKORO_OFFICIAL_MODEL_REPO} · shared Hugging Face cache\n"
        f"[cache] {cache}\n"
        "[ownership] external runtimes and shared cache files are never deleted by DubLocal\n"
        "```"
    )


def prepare_kokoro_runtime() -> str:
    runtime = kokoro_runtime()
    if runtime is not None:
        return runtime.label

    root = _repository_root()
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", f"{root}[kokoro]"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DubLocalError(f"Could not install the optional Kokoro runtime: {message}") from exc

    runtime = kokoro_runtime()
    if runtime is None:
        raise DubLocalError(
            "Kokoro packages were installed, but DubLocal still cannot find a compatible runtime. "
            "Restart DubLocal and try Prepare Kokoro again."
        )
    return runtime.label


def suggested_kokoro_language(language: str | None) -> str | None:
    value = (language or "").strip().replace("_", "-")
    if not value:
        return None
    lower = value.lower()
    if lower.startswith("en-gb"):
        return "en-GB"
    base = lower.split("-", 1)[0]
    return _TRANSLATION_TO_KOKORO.get(base)


def kokoro_voice_choices(language: str | None) -> list[tuple[str, str]]:
    metadata = KOKORO_LANGUAGES.get(str(language or ""))
    if not metadata:
        return []
    return list(metadata["voices"])


def kokoro_default_voice(language: str | None) -> str | None:
    metadata = KOKORO_LANGUAGES.get(str(language or ""))
    if not metadata:
        return None
    return str(metadata["default_voice"])


def _validate_kokoro_selection(language: str, voice: str, speed: float) -> dict[str, Any]:
    metadata = KOKORO_LANGUAGES.get(language)
    if metadata is None:
        supported = ", ".join(item["label"] for item in KOKORO_LANGUAGES.values())
        raise DubLocalError(
            f"Official Kokoro does not support voice language {language!r}. Supported: {supported}."
        )
    if not 0.5 <= speed <= 2.0:
        raise DubLocalError("Kokoro speed must be between 0.5 and 2.0.")

    voice_ids = [item.strip() for item in str(voice or "").split(",") if item.strip()]
    if not voice_ids:
        raise DubLocalError("Choose a Kokoro voice.")
    lang_code = str(metadata["lang_code"])
    mismatched = [item for item in voice_ids if not item.startswith(lang_code)]
    if mismatched:
        raise DubLocalError(
            f"Voice {', '.join(mismatched)} does not match {metadata['label']}. "
            "Choose a voice offered for the selected language."
        )
    return metadata


def _worker_path() -> Path:
    return Path(__file__).with_name("kokoro_worker.py")


def _run_worker(request: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    runtime = kokoro_runtime()
    if runtime is None:
        raise DubLocalError(
            "No compatible Kokoro runtime is available. Open Settings → Model Manager → Kokoro and click Prepare Kokoro."
        )

    request_path = job_dir / "kokoro-request.json"
    response_path = job_dir / "kokoro-response.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    env["HF_HUB_CACHE"] = str(shared_huggingface_cache())

    try:
        completed = subprocess.run(
            [str(runtime.python), str(_worker_path()), str(request_path), str(response_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=6 * 60 * 60,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DubLocalError(f"Could not run the Kokoro worker: {exc}") from exc

    payload: dict[str, Any] | None = None
    if response_path.is_file():
        try:
            loaded = json.loads(response_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, json.JSONDecodeError):
            payload = None

    if completed.returncode != 0 or not payload or not payload.get("ok"):
        detail = ""
        if payload and payload.get("error"):
            detail = str(payload["error"])
        else:
            detail = (completed.stderr or completed.stdout or "Kokoro worker failed").strip()
        raise DubLocalError(f"Kokoro generation failed: {detail}")

    payload["runtime_label"] = runtime.label
    payload["runtime_python"] = str(runtime.python)
    return payload


def prepare_kokoro(language: str, voice: str, speed: float = 1.0) -> str:
    metadata = _validate_kokoro_selection(language, voice, float(speed))
    prepare_kokoro_runtime()
    job_dir = _new_job_dir("prepare-kokoro")
    try:
        response = _run_worker(
            {
                "lang_code": metadata["lang_code"],
                "voice": voice,
                "speed": float(speed),
                "repo_id": KOKORO_OFFICIAL_MODEL_REPO,
                "output_dir": str(job_dir / "segments"),
                "segments": [{"index": 1, "text": _PREPARE_TEXT[language]}],
            },
            job_dir,
        )
        return f"{response['runtime_label']} · {response['device']}"
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def _read_segment_wav(path: Path, expected_rate: int) -> np.ndarray:
    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise DubLocalError(f"Unexpected Kokoro WAV format: {path.name}")
            if handle.getframerate() != expected_rate:
                raise DubLocalError(
                    f"Unexpected Kokoro sample rate {handle.getframerate()} Hz; expected {expected_rate} Hz."
                )
            frames = handle.readframes(handle.getnframes())
    except wave.Error as exc:
        raise DubLocalError(f"Could not read Kokoro segment {path.name}: {exc}") from exc
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def _assemble_voice_track(
    timeline: list[Segment],
    generated: list[VoiceSegmentResult],
    output: Path,
    *,
    sample_rate: int = 24000,
) -> None:
    if not timeline:
        raise DubLocalError("The subtitle timeline is empty.")

    total_ms = max(
        max(segment.end_ms for segment in timeline),
        max((item.start_ms + item.voice_duration_ms for item in generated), default=0),
    )
    total_samples = max(1, int(round(total_ms * sample_rate / 1000)))
    raw_path = output.with_suffix(".mix-f32")
    mix = np.memmap(raw_path, dtype=np.float32, mode="w+", shape=(total_samples,))
    mix[:] = 0.0

    try:
        for item in generated:
            if not item.wav_path.is_file():
                continue
            audio = _read_segment_wav(item.wav_path, sample_rate)
            start = int(round(item.start_ms * sample_rate / 1000))
            end = min(total_samples, start + int(audio.size))
            if end > start:
                mix[start:end] += audio[: end - start]
        mix.flush()

        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            chunk_samples = sample_rate * 20
            for offset in range(0, total_samples, chunk_samples):
                # Copy each chunk out of the mmap so Windows never keeps a live view
                # when the temporary backing file is removed below.
                chunk = np.array(
                    mix[offset : offset + chunk_samples],
                    dtype=np.float32,
                    copy=True,
                )
                pcm = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype("<i2")
                handle.writeframes(pcm.tobytes())
    finally:
        # np.memmap relies on object finalization on POSIX, where unlinking an open
        # mapping is allowed. Windows does not: close the mapping explicitly before
        # removing the temporary file. This is shared by Kokoro and other providers.
        try:
            mix.flush()
        except (OSError, ValueError):
            pass
        mmap_handle = getattr(mix, "_mmap", None)
        if mmap_handle is not None:
            mmap_handle.close()
        del mix
        raw_path.unlink(missing_ok=True)


def generate_voice_track(
    subtitle_path: str | Path,
    *,
    language: str,
    voice: str,
    speed: float = 1.0,
    segment_voices: dict[int, str] | None = None,
) -> VoiceTrackResult:
    source = Path(subtitle_path)
    if not source.is_file():
        raise DubLocalError("Choose an extracted, transcribed or translated SRT first.")
    if source.suffix.lower() != ".srt":
        raise DubLocalError("M4 Kokoro voice generation currently expects an SRT timeline.")

    segment_voices = {int(key): str(value) for key, value in (segment_voices or {}).items() if value}
    all_voices = list(dict.fromkeys([voice, *segment_voices.values()]))
    metadata = _validate_kokoro_selection(language, ",".join(all_voices), float(speed))
    if kokoro_runtime() is None:
        raise DubLocalError(
            "Kokoro is not prepared yet. Open Settings → Model Manager → Kokoro and click Prepare Kokoro first."
        )

    try:
        timeline = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not parse the subtitle timeline: {exc}") from exc
    if not timeline:
        raise DubLocalError("The subtitle timeline contains no spoken segments.")

    job_dir = _new_job_dir("kokoro")
    segment_dir = job_dir / "segments"
    response = _run_worker(
        {
            "lang_code": metadata["lang_code"],
            "voice": voice,
            "speed": float(speed),
            "repo_id": KOKORO_OFFICIAL_MODEL_REPO,
            "output_dir": str(segment_dir),
            "segments": [
                {
                    "index": item.index,
                    "text": item.text,
                    "voice": segment_voices.get(item.index, voice),
                }
                for item in timeline
            ],
        },
        job_dir,
    )

    response_by_index = {
        int(item["index"]): item for item in response.get("segments", []) if "index" in item
    }
    generated: list[VoiceSegmentResult] = []
    for segment in timeline:
        item = response_by_index.get(segment.index)
        if item is None or not item.get("path"):
            raise DubLocalError(f"Kokoro did not return audio for subtitle segment {segment.index}.")
        duration_ms = int(item.get("duration_ms") or 0)
        slot_ms = max(0, segment.end_ms - segment.start_ms)
        generated.append(
            VoiceSegmentResult(
                index=segment.index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                voice_duration_ms=duration_ms,
                slot_ms=slot_ms,
                overflow_ms=max(0, duration_ms - slot_ms),
                wav_path=Path(str(item["path"])),
            )
        )

    safe_language = language.replace("/", "-")
    safe_voice = voice.replace(",", "-").replace("/", "-")
    output = job_dir / f"voice-{safe_language}-{safe_voice}.wav"
    _assemble_voice_track(timeline, generated, output, sample_rate=int(response["sample_rate"]))

    manifest = job_dir / "voice-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "engine": "Kokoro",
                "model": KOKORO_OFFICIAL_MODEL_REPO,
                "runtime": response.get("runtime_label"),
                "runtime_python": response.get("runtime_python"),
                "device": response.get("device"),
                "language": language,
                "lang_code": metadata["lang_code"],
                "voice": voice,
                "segment_voices": segment_voices,
                "speed": float(speed),
                "sample_rate": int(response["sample_rate"]),
                "source_srt": str(source),
                "segments": [
                    {
                        "index": item.index,
                        "start_ms": item.start_ms,
                        "end_ms": item.end_ms,
                        "text": item.text,
                        "voice": segment_voices.get(item.index, voice),
                        "voice_duration_ms": item.voice_duration_ms,
                        "slot_ms": item.slot_ms,
                        "overflow_ms": item.overflow_ms,
                        "wav": str(item.wav_path),
                    }
                    for item in generated
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return VoiceTrackResult(
        wav_path=output,
        manifest_path=manifest,
        segments=generated,
        language=language,
        voice=voice,
        speed=float(speed),
        device=str(response.get("device") or "unknown"),
        runtime_label=str(response.get("runtime_label") or "unknown"),
    )


def voice_segments_to_rows(segments: list[VoiceSegmentResult]) -> list[list[str]]:
    def stamp(milliseconds: int) -> str:
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, millis = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

    return [
        [
            stamp(item.start_ms),
            stamp(item.end_ms),
            f"{item.voice_duration_ms / 1000:.2f}s",
            "OK" if item.overflow_ms == 0 else f"+{item.overflow_ms / 1000:.2f}s",
            item.text,
        ]
        for item in segments
    ]
