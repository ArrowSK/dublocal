from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from . import tts
from .dependencies import discover_python_runtime, local_resource_status, shared_huggingface_cache
from .media import DubLocalError
from .timeline import parse_srt
from .tts_provider_registry import (
    TTSProvider,
    all_providers,
    prepare_provider,
    provider_for_language,
    provider_is_installed,
    provider_status_text,
    register_custom_provider,
    voice_metadata,
)


_RUSSIAN_RUNTIME_MODULES = ("kokoro", "numpy", "torch", "huggingface_hub", "ruaccent")
_ORIGINAL_GENERATE = tts.generate_voice_track
_ORIGINAL_PREPARE = tts.prepare_kokoro
_ORIGINAL_STATUS = tts.kokoro_runtime_status
_ORIGINAL_LANGUAGES = set(tts.KOKORO_LANGUAGES)
_INSTALL_LOCK = threading.RLock()
_INSTALLED = False


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _russian_runtime():
    return discover_python_runtime(_RUSSIAN_RUNTIME_MODULES, allow_current=True)


def _ensure_espeak_ng() -> str:
    executable = shutil.which("espeak-ng") or shutil.which("espeak")
    if executable:
        return executable
    brew = shutil.which("brew")
    if brew and sys.platform == "darwin":
        try:
            subprocess.run(
                [brew, "install", "espeak-ng"],
                check=True,
                capture_output=True,
                text=True,
                timeout=20 * 60,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
            raise DubLocalError(f"Could not install the external eSpeak NG dependency: {detail}") from exc
        executable = shutil.which("espeak-ng") or shutil.which("espeak")
        if executable:
            return executable
    raise DubLocalError(
        "Russian TTS needs the separately installed eSpeak NG command-line tool. "
        "Install eSpeak NG, then click Prepare again. DubLocal does not bundle this GPL dependency."
    )


def _prepare_russian_runtime():
    runtime = _russian_runtime()
    if runtime is None:
        root = _repository_root()
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", f"{root}[kokoro-ru]"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30 * 60,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
            raise DubLocalError(f"Could not install the optional Russian TTS runtime: {detail}") from exc
        runtime = _russian_runtime()
    if runtime is None:
        raise DubLocalError(
            "Russian TTS packages were installed, but no compatible isolated runtime was found. Restart DubLocal and try again."
        )
    _ensure_espeak_ng()
    return runtime


def _worker_path() -> Path:
    return Path(__file__).with_name("tts_provider_worker.py")


def _run_provider_worker(provider: TTSProvider, request: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    if provider.manifest["frontend"] == "russian-v2":
        runtime = _russian_runtime()
        if runtime is None:
            raise DubLocalError("Russian TTS runtime is not prepared. Open Settings → Model Manager and prepare Russian.")
        _ensure_espeak_ng()
    else:
        runtime = tts.kokoro_runtime()
        if runtime is None:
            raise DubLocalError("Kokoro runtime is not prepared for this custom TTS provider.")

    request_path = job_dir / "tts-provider-request.json"
    response_path = job_dir / "tts-provider-response.json"
    payload = dict(request)
    payload["provider_manifest"] = provider.manifest
    payload["provider_root"] = str(provider.install_dir)
    request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

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
        raise DubLocalError(f"Could not run local TTS provider worker: {exc}") from exc

    response: dict[str, Any] | None = None
    if response_path.is_file():
        try:
            loaded = json.loads(response_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                response = loaded
        except (OSError, json.JSONDecodeError):
            response = None
    if completed.returncode != 0 or not response or not response.get("ok"):
        detail = (
            str(response.get("error"))
            if response and response.get("error")
            else (completed.stderr or completed.stdout or "provider worker failed").strip()
        )
        raise DubLocalError(f"Local TTS provider generation failed: {detail}")
    response["runtime_label"] = runtime.label
    response["runtime_python"] = str(runtime.python)
    return response


def _provider_language_metadata(provider: TTSProvider) -> dict[str, Any]:
    voices = [(item["label"], item["id"]) for item in provider.voices]
    prefix = "r" if provider.manifest["frontend"] == "russian-v2" else str(provider.manifest["frontend"]).rsplit("-", 1)[-1]
    return {
        "label": f"{provider.manifest['language_label']} · {'third-party' if provider.language == 'ru' else 'custom'}",
        "lang_code": prefix,
        "default_voice": provider.manifest["default_voice"],
        "voices": voices,
        "provider_id": provider.id,
    }


def _apply_provider_metadata() -> None:
    # Russian is visible before installation so the normal language selector can
    # guide the user to Prepare. Other languages are overridden only by an already
    # prepared custom provider; an unprepared custom manifest never disables the
    # stable official Kokoro path.
    russian = provider_for_language("ru", require_installed=False)
    if russian is not None:
        tts.KOKORO_LANGUAGES["ru"] = _provider_language_metadata(russian)
        tts._PREPARE_TEXT["ru"] = "Готово."
        tts._TRANSLATION_TO_KOKORO["ru"] = "ru"

    for provider in all_providers():
        if provider.language == "ru" or not provider_is_installed(provider):
            continue
        selected = provider_for_language(provider.language, require_installed=True)
        if selected and selected.id == provider.id:
            tts.KOKORO_LANGUAGES[provider.language] = _provider_language_metadata(provider)
            tts._TRANSLATION_TO_KOKORO[provider.language.split("-", 1)[0].lower()] = provider.language

    tts.KOKORO_LANGUAGE_CHOICES[:] = [
        (metadata["label"], code) for code, metadata in tts.KOKORO_LANGUAGES.items()
    ]


def _provider_selected_for_generation(language: str) -> TTSProvider | None:
    return provider_for_language(language, require_installed=True)


def generate_voice_track_provider_aware(
    subtitle_path: str | Path,
    *,
    language: str,
    voice: str,
    speed: float = 1.0,
    segment_voices: dict[int, str] | None = None,
):
    provider = _provider_selected_for_generation(language)
    if provider is None:
        # Preserve every existing official Kokoro code path. Russian has no official
        # route, so an unprepared Russian provider gets an actionable error instead.
        if language in _ORIGINAL_LANGUAGES:
            return _ORIGINAL_GENERATE(
                subtitle_path,
                language=language,
                voice=voice,
                speed=speed,
                segment_voices=segment_voices,
            )
        registered = provider_for_language(language, require_installed=False)
        if registered is not None:
            raise DubLocalError(
                f"{registered.label} is registered for {language} but is not prepared. "
                "Open Settings → Model Manager and prepare the TTS provider first."
            )
        raise DubLocalError(f"No local TTS provider is registered for voice language {language!r}.")

    if not 0.5 <= float(speed) <= 2.0:
        raise DubLocalError("TTS speed must be between 0.5 and 2.0.")
    voice_ids = [str(voice), *[str(value) for value in (segment_voices or {}).values()]]
    for voice_id in voice_ids:
        voice_metadata(provider, voice_id)

    source = Path(subtitle_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".srt":
        raise DubLocalError("Local TTS providers require a timed SRT subtitle file.")
    try:
        timeline = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not parse the subtitle timeline: {exc}") from exc
    if not timeline:
        raise DubLocalError("The subtitle timeline contains no spoken segments.")

    job_dir = tts._new_job_dir(f"tts-{provider.id}")
    segment_dir = job_dir / "segments"
    plan = {int(key): str(value) for key, value in (segment_voices or {}).items()}
    response = _run_provider_worker(
        provider,
        {
            "voice": voice,
            "speed": float(speed),
            "adaptive_timing": True,
            "device": "cpu" if provider.manifest["frontend"] == "russian-v2" else "cpu",
            "output_dir": str(segment_dir),
            "segments": [
                {
                    "index": item.index,
                    "text": item.text,
                    "voice": plan.get(item.index, voice),
                    "target_duration_ms": max(1, item.end_ms - item.start_ms),
                }
                for item in timeline
            ],
        },
        job_dir,
    )

    by_index = {
        int(item["index"]): item
        for item in response.get("segments", [])
        if isinstance(item, dict) and "index" in item
    }
    generated: list[tts.VoiceSegmentResult] = []
    manifest_segments: list[dict[str, Any]] = []
    for segment in timeline:
        item = by_index.get(segment.index)
        if not item or not item.get("path"):
            raise DubLocalError(f"TTS provider did not return audio for subtitle segment {segment.index}.")
        wav = Path(str(item["path"]))
        duration = int(item.get("duration_ms") or 0)
        slot = max(0, segment.end_ms - segment.start_ms)
        generated.append(
            tts.VoiceSegmentResult(
                index=segment.index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                voice_duration_ms=duration,
                slot_ms=slot,
                overflow_ms=max(0, duration - slot),
                wav_path=wav,
            )
        )
        manifest_segments.append(
            {
                "index": segment.index,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": segment.text,
                "voice": plan.get(segment.index, voice),
                "voice_duration_ms": duration,
                "slot_ms": slot,
                "overflow_ms": max(0, duration - slot),
                "wav": str(wav),
                "native_speed": float(item.get("speed") or speed),
                "pilot_duration_ms": int(item.get("pilot_duration_ms") or duration),
                "target_duration_ms": int(item.get("target_duration_ms") or slot),
                "timing_error_ms": int(item.get("timing_error_ms") or 0),
                "generation_passes": int(item.get("generation_passes") or 1),
            }
        )

    safe_language = language.replace("/", "-")
    safe_voice = voice.replace(",", "-").replace("/", "-")
    output = job_dir / f"voice-{safe_language}-{safe_voice}.wav"
    tts._assemble_voice_track(timeline, generated, output, sample_rate=int(response["sample_rate"]))
    manifest = job_dir / "voice-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "engine": "local-tts-provider",
                "provider_id": provider.id,
                "provider_label": provider.label,
                "provider_license": provider.manifest["license"],
                "provider_receipt": str(provider.receipt_path),
                "runtime": response.get("runtime_label"),
                "runtime_python": response.get("runtime_python"),
                "device": response.get("device"),
                "language": language,
                "voice": voice,
                "segment_voices": plan,
                "speed": float(speed),
                "sample_rate": int(response["sample_rate"]),
                "source_srt": str(source),
                "timing_mode": "native_kokoro_speed",
                "adaptive_timing": True,
                "post_stretch": False,
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
        language=language,
        voice=voice,
        speed=float(speed),
        device=str(response.get("device") or "cpu"),
        runtime_label=f"{provider.label} · {response.get('runtime_label') or 'local runtime'}",
    )


def prepare_kokoro_provider_aware(language: str, voice: str, speed: float = 1.0) -> str:
    provider = provider_for_language(language, require_installed=False)
    if provider is None or (language in _ORIGINAL_LANGUAGES and not provider.manifest.get("preferred")):
        return _ORIGINAL_PREPARE(language, voice, speed)

    # For official languages, preserve the official path unless a custom provider is
    # explicitly preferred. Russian has no official fallback and always prepares its
    # selected registered provider.
    if language in _ORIGINAL_LANGUAGES and provider.builtin:
        return _ORIGINAL_PREPARE(language, voice, speed)

    with _INSTALL_LOCK:
        if provider.manifest["frontend"] == "russian-v2":
            runtime = _prepare_russian_runtime()
        else:
            tts.prepare_kokoro_runtime()
            runtime = tts.kokoro_runtime()
            if runtime is None:
                raise DubLocalError("Kokoro runtime could not be prepared for custom provider.")
        prepare_provider(provider)

        # Generate one tiny utterance. For Russian this also preloads RUAccent into
        # the provider's persistent workdir, so normal generation is not dependent
        # on the kokoro-ru fork remaining online after preparation.
        job_dir = tts._new_job_dir(f"prepare-{provider.id}")
        try:
            response = _run_provider_worker(
                provider,
                {
                    "voice": voice,
                    "speed": float(speed),
                    "adaptive_timing": False,
                    "device": "cpu",
                    "output_dir": str(job_dir / "segments"),
                    "segments": [
                        {
                            "index": 1,
                            "text": tts._PREPARE_TEXT.get(language, "Ready."),
                            "voice": voice,
                        }
                    ],
                },
                job_dir,
            )
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
    return f"{provider.label} · {runtime.label} · {response.get('device', 'cpu')}"


def kokoro_runtime_status_provider_aware() -> str:
    return (
        _ORIGINAL_STATUS()
        + "\n"
        + provider_status_text()
        + "\n```text\n[Russian frontend] RUAccent (MIT) + separately installed eSpeak NG executable; eSpeak is not bundled by DubLocal\n```"
    )


def register_custom_provider_ui(manifest_text: str) -> tuple[str, str]:
    try:
        provider = register_custom_provider(manifest_text)
        action = (
            "```text\n"
            f"[done] registered custom TTS provider {provider.id}\n"
            "[security] data-only manifest accepted · no Python/module/command plugin loaded\n"
            "[next] restart DubLocal, then prepare this provider from the provider manager\n"
            "```"
        )
    except Exception as exc:
        action = f"```text\n[error] {exc}\n```"
    return provider_status_text(), action


def prepare_registered_provider_ui(provider_id: str) -> tuple[str, str]:
    provider = next((item for item in all_providers() if item.id == provider_id), None)
    if provider is None:
        return provider_status_text(), "```text\n[error] Select a registered TTS provider.\n```"
    try:
        if provider.manifest["frontend"] == "russian-v2":
            _prepare_russian_runtime()
        else:
            tts.prepare_kokoro_runtime()
        prepare_provider(provider)
        action = (
            "```text\n"
            f"[done] prepared {provider.label}\n"
            f"[local] {provider.install_dir}\n"
            "[resilience] future generation uses this persistent local snapshot\n"
            "[next] restart DubLocal to make an overriding custom provider active in language/voice selectors\n"
            "```"
        )
    except Exception as exc:
        action = f"```text\n[error] {exc}\n```"
    return provider_status_text(), action


def registered_provider_choices() -> list[tuple[str, str]]:
    return [
        (f"{item.manifest['language_label']} · {item.label}", item.id)
        for item in all_providers()
    ]


def install_tts_provider_refinement() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _apply_provider_metadata()
    tts.generate_voice_track = generate_voice_track_provider_aware
    tts.prepare_kokoro = prepare_kokoro_provider_aware
    tts.kokoro_runtime_status = kokoro_runtime_status_provider_aware
    _INSTALLED = True
