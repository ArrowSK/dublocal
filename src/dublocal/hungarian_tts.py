from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
from platformdirs import user_data_dir

from . import tts
from .media import DubLocalError
from .timeline import parse_srt


HUNGARIAN_LANGUAGE = "hu"
PIPER_RUNTIME_VERSION = "1.7.0"
PIPER_VOICE_REPO = "rhasspy/piper-voices"
# Immutable Piper voice repository revision. Hungarian Anna/Berta/Imre are present
# here and their model/config files are additionally checked below.
PIPER_VOICE_REVISION = "de3dcfdf1912bb49726dc4aa11c26017ce2ac62a"
_SAMPLE_RATE = 22_050
_MACOS_SYSTEM_PREFIX = "hu_macos_"


@dataclass(frozen=True, slots=True)
class PiperVoiceSpec:
    voice_id: str
    label: str
    model_path: str
    config_path: str
    model_sha256: str
    model_md5: str
    config_md5: str


@dataclass(frozen=True, slots=True)
class MacOSVoice:
    voice_id: str
    label: str
    name: str
    locale: str


PIPER_VOICES: tuple[PiperVoiceSpec, ...] = (
    PiperVoiceSpec(
        voice_id="uf_anna",
        label="Anna · female · Piper",
        model_path="hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx",
        config_path="hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx.json",
        model_sha256="968c0c3a66cb667811242cc88653bff9247395fc7a0517fbeef7d8c08cdae62a",
        model_md5="3796f9fa28bd8d390d17828e2e2e952d",
        config_md5="ae63867e2c2cb6695555a17bdee8b751",
    ),
    PiperVoiceSpec(
        voice_id="uf_berta",
        label="Berta · female · Piper",
        model_path="hu/hu_HU/berta/medium/hu_HU-berta-medium.onnx",
        config_path="hu/hu_HU/berta/medium/hu_HU-berta-medium.onnx.json",
        model_sha256="4eed05f767573b77fd2c07e6bccaa9b3c77089a55b9239c3099ecd3d17a59be3",
        model_md5="a94cc2562ba892f462cb502f9d3c3ca3",
        config_md5="1f722cc72f330e3ba0222c6a94a527fa",
    ),
    PiperVoiceSpec(
        voice_id="um_imre",
        label="Imre · male · Piper",
        model_path="hu/hu_HU/imre/medium/hu_HU-imre-medium.onnx",
        config_path="hu/hu_HU/imre/medium/hu_HU-imre-medium.onnx.json",
        model_sha256="af7d98e2031b4f00cf3693cafc47b0b5347f23c28cd6a5957a693f76d7202c2d",
        model_md5="aa0b1d1fdd539881c64ed249097e75ff",
        config_md5="9b6974c685cd8289619660f5e078de06",
    ),
)


def _data_root() -> Path:
    root = Path(user_data_dir("DubLocal")) / "tts-providers" / "hungarian"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _runtime_root() -> Path:
    root = Path(user_data_dir("DubLocal")) / "tts-runtimes" / f"piper-{PIPER_RUNTIME_VERSION}"
    root.parent.mkdir(parents=True, exist_ok=True)
    return root


def _runtime_python(root: Path | None = None) -> Path:
    target = root or _runtime_root()
    if os.name == "nt":
        return target / "Scripts" / "python.exe"
    return target / "bin" / "python"


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _piper_spec(voice_id: str) -> PiperVoiceSpec:
    for item in PIPER_VOICES:
        if item.voice_id == voice_id:
            return item
    raise DubLocalError(f"Unknown Hungarian Piper voice: {voice_id!r}.")


def _voice_install_dir(spec: PiperVoiceSpec) -> Path:
    return _data_root() / "piper" / spec.voice_id


def _voice_paths(spec: PiperVoiceSpec) -> tuple[Path, Path]:
    root = _voice_install_dir(spec)
    return root / Path(spec.model_path).name, root / Path(spec.config_path).name


def _voice_ready(spec: PiperVoiceSpec) -> bool:
    model, config = _voice_paths(spec)
    if not model.is_file() or not config.is_file():
        return False
    try:
        return (
            _digest(model, "sha256") == spec.model_sha256
            and _digest(model, "md5") == spec.model_md5
            and _digest(config, "md5") == spec.config_md5
        )
    except OSError:
        return False


def _piper_runtime_ready() -> bool:
    python = _runtime_python()
    if not python.is_file():
        return False
    try:
        check = subprocess.run(
            [str(python), "-c", "import piper; print(piper.__name__)"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return check.returncode == 0


def _prepare_piper_runtime() -> Path:
    if _piper_runtime_ready():
        return _runtime_python()

    root = _runtime_root()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    try:
        context = venv.EnvBuilder(with_pip=True, clear=True).ensure_directories(root)
        venv.EnvBuilder(with_pip=True, clear=False).create(root)
        python = Path(context.env_exe)
        if not python.is_file():
            python = _runtime_python(root)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                f"piper-tts=={PIPER_RUNTIME_VERSION}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30 * 60,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
        raise DubLocalError(f"Could not prepare the isolated Piper runtime: {detail}") from exc

    if not _piper_runtime_ready():
        raise DubLocalError(
            "Piper was installed into DubLocal's isolated TTS runtime, but the runtime could not be verified."
        )
    return _runtime_python()


def _prepare_piper_voice(voice_id: str) -> tuple[Path, Path]:
    spec = _piper_spec(voice_id)
    if _voice_ready(spec):
        return _voice_paths(spec)

    root = _voice_install_dir(spec)
    staging = Path(tempfile.mkdtemp(prefix=f".{spec.voice_id}-", dir=_data_root()))
    try:
        model_cached = Path(
            hf_hub_download(
                repo_id=PIPER_VOICE_REPO,
                revision=PIPER_VOICE_REVISION,
                filename=spec.model_path,
            )
        )
        config_cached = Path(
            hf_hub_download(
                repo_id=PIPER_VOICE_REPO,
                revision=PIPER_VOICE_REVISION,
                filename=spec.config_path,
            )
        )
        model = staging / Path(spec.model_path).name
        config = staging / Path(spec.config_path).name
        shutil.copy2(model_cached, model)
        shutil.copy2(config_cached, config)

        if _digest(model, "sha256") != spec.model_sha256 or _digest(model, "md5") != spec.model_md5:
            raise DubLocalError(f"Downloaded Piper model failed integrity verification for {spec.label}.")
        if _digest(config, "md5") != spec.config_md5:
            raise DubLocalError(f"Downloaded Piper config failed integrity verification for {spec.label}.")

        receipt = {
            "provider": "Piper",
            "runtime_package": f"piper-tts=={PIPER_RUNTIME_VERSION}",
            "voice": spec.voice_id,
            "repo_id": PIPER_VOICE_REPO,
            "revision": PIPER_VOICE_REVISION,
            "model_sha256": spec.model_sha256,
            "model_md5": spec.model_md5,
            "config_md5": spec.config_md5,
            "model_license": "MIT",
            "dataset_license": "CC0",
            "runtime_license": "GPL-3.0-or-later external isolated runtime",
        }
        (staging / "install-receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        root.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if not _voice_ready(spec):
        raise DubLocalError(f"Prepared Piper voice did not pass verification: {spec.label}.")
    return _voice_paths(spec)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "voice"


def macos_hungarian_voices() -> list[MacOSVoice]:
    if sys.platform != "darwin":
        return []
    say = shutil.which("say")
    if not say:
        return []
    try:
        result = subprocess.run(
            [say, "-v", "?"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    voices: list[MacOSVoice] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(?P<name>.+?)\s+(?P<locale>[a-z]{2}_[A-Z]{2})\s+#")
    for line in result.stdout.splitlines():
        match = pattern.match(line.strip())
        if not match or match.group("locale").lower() != "hu_hu":
            continue
        name = match.group("name").strip()
        voice_id = f"{_MACOS_SYSTEM_PREFIX}{_slug(name)}"
        if voice_id in seen:
            continue
        seen.add(voice_id)
        voices.append(
            MacOSVoice(
                voice_id=voice_id,
                label=f"{name} · macOS system voice",
                name=name,
                locale=match.group("locale"),
            )
        )

    # Tünde is the longstanding Hungarian macOS voice when installed. Prefer it
    # without assuming that every macOS release exposes the same voice catalogue.
    voices.sort(key=lambda item: (0 if item.name.casefold() == "tünde" else 1, item.name.casefold()))
    return voices


def _macos_voice(voice_id: str) -> MacOSVoice:
    for item in macos_hungarian_voices():
        if item.voice_id == voice_id:
            return item
    raise DubLocalError(
        "The selected Hungarian macOS voice is not installed. Choose a Piper voice or install a Hungarian system voice in macOS."
    )


def is_macos_system_voice(voice_id: str) -> bool:
    return str(voice_id or "").startswith(_MACOS_SYSTEM_PREFIX)


def hungarian_voice_choices() -> list[tuple[str, str]]:
    choices = [(voice.label, voice.voice_id) for voice in macos_hungarian_voices()]
    choices.extend((item.label, item.voice_id) for item in PIPER_VOICES)
    return choices


def hungarian_default_voice() -> str:
    system = macos_hungarian_voices()
    if system:
        return system[0].voice_id
    return PIPER_VOICES[0].voice_id


def install_hungarian_metadata() -> None:
    tts.KOKORO_LANGUAGES[HUNGARIAN_LANGUAGE] = {
        "label": "Hungarian",
        "lang_code": "u",
        "default_voice": hungarian_default_voice(),
        "voices": hungarian_voice_choices(),
        "provider_id": "hungarian-local-auto",
    }
    tts._PREPARE_TEXT[HUNGARIAN_LANGUAGE] = "Készen áll."
    tts._TRANSLATION_TO_KOKORO[HUNGARIAN_LANGUAGE] = HUNGARIAN_LANGUAGE
    tts.KOKORO_LANGUAGE_CHOICES[:] = [
        (metadata["label"], code) for code, metadata in tts.KOKORO_LANGUAGES.items()
    ]


def hungarian_status_text() -> str:
    system = macos_hungarian_voices()
    runtime = "ready" if _piper_runtime_ready() else "not prepared"
    piper = ", ".join(
        f"{item.label.split(' · ', 1)[0]}={'ready' if _voice_ready(item) else 'not prepared'}"
        for item in PIPER_VOICES
    )
    if sys.platform == "darwin":
        system_line = (
            "available · " + ", ".join(item.name for item in system)
            if system
            else "not installed · Piper will be used"
        )
    else:
        system_line = "not applicable on this platform · Piper is the Hungarian provider"
    return (
        "```text\n"
        f"[Hungarian] Auto · macOS system voice when available; Piper elsewhere/fallback\n"
        f"[macOS system] {system_line}\n"
        f"[Piper runtime] {runtime} · isolated piper-tts {PIPER_RUNTIME_VERSION}\n"
        f"[Piper voices] {piper}\n"
        "[voice data] rhasspy/piper-voices · MIT model repository · Hungarian datasets marked CC0\n"
        "[runtime boundary] Piper GPL runtime is installed separately and invoked out-of-process\n"
        "```"
    )


def prepare_hungarian_tts(voice: str, speed: float = 1.0) -> str:
    if not 0.5 <= float(speed) <= 2.0:
        raise DubLocalError("TTS speed must be between 0.5 and 2.0.")
    if is_macos_system_voice(voice):
        selected = _macos_voice(voice)
        _prepare_macos_voice(selected, float(speed))
        return f"macOS system voice · {selected.name} · local"

    spec = _piper_spec(voice)
    python = _prepare_piper_runtime()
    _prepare_piper_voice(spec.voice_id)
    return f"Piper {PIPER_RUNTIME_VERSION} · {spec.label} · {python}"


def _measure_wav_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise DubLocalError(f"Unexpected Hungarian TTS WAV format: {path.name}")
    except wave.Error as exc:
        raise DubLocalError(f"Could not read generated Hungarian speech: {exc}") from exc
    return max(1, int(round(frames * 1000 / max(1, rate))))


def _synthesize_piper(text: str, voice_id: str, speed: float, output: Path) -> None:
    python = _prepare_piper_runtime()
    model, config = _prepare_piper_voice(voice_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    length_scale = 1.0 / max(0.5, min(2.0, float(speed)))
    command = [
        str(python),
        "-m",
        "piper",
        "--model",
        str(model),
        "--config",
        str(config),
        "--output_file",
        str(output),
        "--length-scale",
        f"{length_scale:.5f}",
    ]
    try:
        result = subprocess.run(
            command,
            input=text,
            capture_output=True,
            text=True,
            check=False,
            timeout=10 * 60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DubLocalError(f"Could not run Piper Hungarian TTS: {exc}") from exc
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 64:
        detail = (result.stderr or result.stdout or "Piper returned no WAV output").strip()
        raise DubLocalError(f"Piper Hungarian TTS failed: {detail}")


def _synthesize_macos(text: str, voice: MacOSVoice, speed: float, output: Path) -> None:
    if sys.platform != "darwin":
        raise DubLocalError("macOS system speech is only available on macOS.")
    say = shutil.which("say")
    ffmpeg = shutil.which("ffmpeg")
    if not say or not ffmpeg:
        raise DubLocalError("Hungarian macOS speech needs the macOS 'say' tool and FFmpeg.")
    output.parent.mkdir(parents=True, exist_ok=True)
    aiff = output.with_suffix(".aiff")
    words_per_minute = max(80, min(360, int(round(175 * float(speed)))))
    try:
        spoken = subprocess.run(
            [say, "-v", voice.name, "-r", str(words_per_minute), "-o", str(aiff)],
            input=text,
            capture_output=True,
            text=True,
            check=False,
            timeout=5 * 60,
        )
        if spoken.returncode != 0 or not aiff.is_file():
            detail = (spoken.stderr or spoken.stdout or "macOS speech returned no audio").strip()
            raise DubLocalError(f"macOS Hungarian speech failed: {detail}")
        converted = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(aiff),
                "-ac",
                "1",
                "-ar",
                str(_SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5 * 60,
        )
        if converted.returncode != 0 or not output.is_file() or output.stat().st_size < 64:
            detail = (converted.stderr or converted.stdout or "FFmpeg returned no WAV output").strip()
            raise DubLocalError(f"Could not convert macOS Hungarian speech to WAV: {detail}")
    finally:
        aiff.unlink(missing_ok=True)


def _prepare_macos_voice(voice: MacOSVoice, speed: float) -> None:
    job = Path(tempfile.mkdtemp(prefix="dublocal-hu-macos-"))
    try:
        output = job / "probe.wav"
        _synthesize_macos("Készen áll.", voice, speed, output)
        _measure_wav_ms(output)
    finally:
        shutil.rmtree(job, ignore_errors=True)


def _synthesize_once(text: str, voice_id: str, speed: float, output: Path) -> str:
    if is_macos_system_voice(voice_id):
        selected = _macos_voice(voice_id)
        _synthesize_macos(text, selected, speed, output)
        return f"macOS system · {selected.name}"
    _synthesize_piper(text, voice_id, speed, output)
    return f"Piper · {_piper_spec(voice_id).label.split(' · ', 1)[0]}"


def generate_hungarian_voice_track(
    subtitle_path: str | Path,
    *,
    voice: str,
    speed: float = 1.0,
    segment_voices: dict[int, str] | None = None,
):
    if not 0.5 <= float(speed) <= 2.0:
        raise DubLocalError("TTS speed must be between 0.5 and 2.0.")
    source = Path(subtitle_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".srt":
        raise DubLocalError("Hungarian voice generation requires a timed SRT subtitle file.")
    try:
        timeline = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not parse the subtitle timeline: {exc}") from exc
    if not timeline:
        raise DubLocalError("The subtitle timeline contains no spoken segments.")

    planned = {int(key): str(value) for key, value in (segment_voices or {}).items() if value}
    selected_ids = {voice, *planned.values()}
    for voice_id in selected_ids:
        if is_macos_system_voice(voice_id):
            _macos_voice(voice_id)
        else:
            _piper_spec(voice_id)

    # Preserve the normal explicit preparation policy: generation does not silently
    # install a model/runtime. macOS system voices need no model preparation.
    piper_ids = [item for item in selected_ids if not is_macos_system_voice(item)]
    if piper_ids:
        missing = [item for item in piper_ids if not _voice_ready(_piper_spec(item))]
        if not _piper_runtime_ready() or missing:
            names = ", ".join(_piper_spec(item).label.split(" · ", 1)[0] for item in missing) or "runtime"
            raise DubLocalError(
                "Hungarian Piper voice generation is not prepared. Open Settings → Model Manager → Voice engines, "
                f"choose the Hungarian voice ({names}) and click Prepare / verify voice engine."
            )

    job_dir = tts._new_job_dir("hungarian")
    segment_dir = job_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    generated: list[tts.VoiceSegmentResult] = []
    manifest_segments: list[dict[str, Any]] = []
    runtime_labels: set[str] = set()

    for segment in timeline:
        selected_voice = planned.get(segment.index, voice)
        target_ms = max(1, segment.end_ms - segment.start_ms)
        output = segment_dir / f"segment-{segment.index:06d}.wav"
        effective_speed = float(speed)
        runtime_labels.add(_synthesize_once(segment.text, selected_voice, effective_speed, output))
        pilot_ms = _measure_wav_ms(output)
        duration_ms = pilot_ms
        passes = 1

        tolerance = max(120, int(round(target_ms * 0.07)))
        if duration_ms > target_ms + tolerance:
            needed = effective_speed * duration_ms / target_ms
            adjusted_speed = min(2.0, max(effective_speed, needed))
            if adjusted_speed >= effective_speed + 0.03:
                runtime_labels.add(_synthesize_once(segment.text, selected_voice, adjusted_speed, output))
                effective_speed = adjusted_speed
                duration_ms = _measure_wav_ms(output)
                passes = 2

        generated.append(
            tts.VoiceSegmentResult(
                index=segment.index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                voice_duration_ms=duration_ms,
                slot_ms=target_ms,
                overflow_ms=max(0, duration_ms - target_ms),
                wav_path=output,
            )
        )
        manifest_segments.append(
            {
                "index": segment.index,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": segment.text,
                "voice": selected_voice,
                "voice_duration_ms": duration_ms,
                "slot_ms": target_ms,
                "overflow_ms": max(0, duration_ms - target_ms),
                "wav": str(output),
                "native_speed": effective_speed,
                "pilot_duration_ms": pilot_ms,
                "target_duration_ms": target_ms,
                "timing_error_ms": duration_ms - target_ms,
                "generation_passes": passes,
            }
        )

    safe_voice = re.sub(r"[^a-zA-Z0-9._-]+", "-", voice).strip("-") or "hu"
    output = job_dir / f"voice-hu-{safe_voice}.wav"
    tts._assemble_voice_track(timeline, generated, output, sample_rate=_SAMPLE_RATE)
    manifest = job_dir / "voice-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "engine": "Hungarian local TTS",
                "language": HUNGARIAN_LANGUAGE,
                "voice": voice,
                "segment_voices": planned,
                "speed": float(speed),
                "sample_rate": _SAMPLE_RATE,
                "source_srt": str(source),
                "timing_mode": "native_provider_speed",
                "adaptive_timing": True,
                "post_stretch": False,
                "runtime": sorted(runtime_labels),
                "piper": {
                    "package": f"piper-tts=={PIPER_RUNTIME_VERSION}",
                    "repo_id": PIPER_VOICE_REPO,
                    "revision": PIPER_VOICE_REVISION,
                    "runtime_boundary": "isolated out-of-process GPL runtime",
                    "voice_model_license": "MIT",
                    "dataset_license": "CC0",
                },
                "macos_system_voice": {
                    "availability": "OS-provided only on macOS",
                    "redistribution_rights": "not asserted by DubLocal; system/vendor terms apply",
                },
                "segments": manifest_segments,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return tts.VoiceTrackResult(
        wav_path=output,
        manifest_path=manifest,
        segments=generated,
        language=HUNGARIAN_LANGUAGE,
        voice=voice,
        speed=float(speed),
        device="system/cpu" if any(is_macos_system_voice(item) for item in selected_ids) else "cpu",
        runtime_label=" + ".join(sorted(runtime_labels)),
    )
