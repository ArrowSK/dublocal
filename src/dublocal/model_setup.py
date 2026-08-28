from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from platformdirs import user_config_dir

from .adaptive_contextual import (
    contextual_model_spec,
    contextual_model_valid,
    install_contextual_model_for,
)
from .contextual_translation import install_llama_cpp
from .hardware_profile import (
    HardwareProfile,
    detect_hardware_profile,
    hardware_summary,
    recommend_translation_profile,
)
from .media import DubLocalError
from .progress_operations import install_whisper_model_with_progress
from .transcription import WHISPER_MODELS, whisper_model_path
from .tts import kokoro_default_voice, kokoro_runtime, prepare_kokoro


ProgressCallback = Callable[[float, str], None]
_STATE_SCHEMA = 1
_KOKORO_ESTIMATE_GB = 0.4


@dataclass(frozen=True, slots=True)
class ModelSetupRecommendation:
    hardware: HardwareProfile
    whisper_model_id: str
    whisper_label: str
    whisper_size: str
    translation_model_key: str
    translation_label: str
    translation_size: str
    translation_explanation: str
    approximate_model_gb: float


@dataclass(frozen=True, slots=True)
class ModelSetupState:
    recommendation: ModelSetupRecommendation
    whisper_ready: bool
    translation_ready: bool
    voice_ready: bool
    first_run_pending: bool

    @property
    def ready(self) -> bool:
        return self.whisper_ready and self.translation_ready and self.voice_ready


def setup_state_path() -> Path:
    root = Path(user_config_dir("DubLocal"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "model-setup.json"


def _read_state() -> dict[str, object]:
    path = setup_state_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(**updates: object) -> None:
    current = _read_state()
    current.update(updates)
    current["schema_version"] = _STATE_SCHEMA
    path = setup_state_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _size_gb(value: str) -> float:
    text = str(value).strip().lower()
    try:
        number = float(text.split()[0])
    except (ValueError, IndexError):
        return 0.0
    if "mib" in text or "mb" in text:
        return number / 1024.0
    if "gib" in text or "gb" in text:
        return number
    return 0.0


def recommended_whisper_model(profile: HardwareProfile | None = None) -> str:
    hardware = profile or detect_hardware_profile()
    # Apple Silicon can run the quantized Turbo model comfortably and gains useful
    # accuracy on accents/music/noisy material. Intel and unknown hosts keep the
    # lighter Base model as the conservative first-run default.
    return "large-v3-turbo-q5_0" if hardware.apple_silicon else "base"


def recommended_model_setup(
    profile: HardwareProfile | None = None,
) -> ModelSetupRecommendation:
    hardware = profile or detect_hardware_profile()
    whisper_id = recommended_whisper_model(hardware)
    whisper = WHISPER_MODELS[whisper_id]
    translation = recommend_translation_profile(hardware)
    translation_spec = contextual_model_spec(translation.model_key)
    approximate = (
        _size_gb(str(whisper["size"]))
        + _size_gb(str(translation_spec.metadata["size"]))
        + _KOKORO_ESTIMATE_GB
    )
    return ModelSetupRecommendation(
        hardware=hardware,
        whisper_model_id=whisper_id,
        whisper_label=str(whisper["label"]).split(" · ")[0],
        whisper_size=str(whisper["size"]),
        translation_model_key=translation.model_key,
        translation_label=str(translation_spec.metadata["label"]),
        translation_size=str(translation_spec.metadata["size"]),
        translation_explanation=translation.explanation,
        approximate_model_gb=approximate,
    )


def model_setup_state(profile: HardwareProfile | None = None) -> ModelSetupState:
    recommendation = recommended_model_setup(profile)
    marker = _read_state()
    return ModelSetupState(
        recommendation=recommendation,
        whisper_ready=whisper_model_path(recommendation.whisper_model_id).is_file(),
        translation_ready=contextual_model_valid(recommendation.translation_model_key),
        # Runtime presence alone does not prove that Kokoro model/voice assets were
        # actually exercised, so the wizard records a successful preparation receipt.
        voice_ready=bool(marker.get("voice_prepared")) and kokoro_runtime() is not None,
        first_run_pending=not bool(marker.get("first_run_seen")),
    )


def mark_first_run_skipped() -> None:
    _write_state(
        first_run_seen=True,
        skipped=True,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def _status_word(ready: bool) -> str:
    return "Ready" if ready else "Needs setup"


def model_setup_summary(profile: HardwareProfile | None = None) -> str:
    state = model_setup_state(profile)
    rec = state.recommendation
    return (
        f"### Recommended for this Mac\n"
        f"**{hardware_summary(rec.hardware)}**\n\n"
        f"- **Subtitles:** {rec.whisper_label} · {rec.whisper_size} — **{_status_word(state.whisper_ready)}**\n"
        f"- **Translation:** {rec.translation_label} · {rec.translation_size} — **{_status_word(state.translation_ready)}**\n"
        f"- **Voice-over:** Kokoro 82M · local voice assets — **{_status_word(state.voice_ready)}**\n\n"
        f"Approximate model data for the recommended setup: **{rec.approximate_model_gb:.1f} GB**. "
        "Kokoro's Python runtime can require additional disk space.\n\n"
        f"**Why this translation model:** {rec.translation_explanation}"
    )


def prepare_recommended_models(
    *,
    progress_callback: ProgressCallback | None = None,
) -> str:
    rec = recommended_model_setup()

    def progress(value: float, text: str) -> None:
        if progress_callback:
            progress_callback(max(0.0, min(1.0, value)), text)

    progress(0.02, "Checking recommended model setup")

    try:
        def whisper_progress(fraction: float, label: str) -> None:
            progress(0.04 + 0.28 * fraction, label)

        install_whisper_model_with_progress(
            rec.whisper_model_id,
            progress_callback=whisper_progress,
        )

        progress(0.34, "Preparing local translation engine")
        install_llama_cpp()
        progress(
            0.40,
            f"Preparing {rec.translation_label} · largest model download",
        )
        install_contextual_model_for(rec.translation_model_key)
        progress(0.78, "Translation model ready")

        progress(0.80, "Preparing Kokoro voice engine and default voice")
        voice = kokoro_default_voice("en-US") or "af_heart"
        prepare_kokoro("en-US", voice, 1.0)
        progress(0.97, "Voice engine ready")
    except Exception as exc:
        message = str(exc) if isinstance(exc, DubLocalError) else f"Unexpected setup error: {exc}"
        raise DubLocalError(
            f"Recommended model setup stopped: {message}. Components already prepared were kept; run Model Setup again to continue."
        ) from exc

    _write_state(
        first_run_seen=True,
        skipped=False,
        voice_prepared=True,
        completed_at=datetime.now(timezone.utc).isoformat(),
        whisper_model_id=rec.whisper_model_id,
        translation_model_key=rec.translation_model_key,
    )
    progress(1.0, "Recommended model setup complete")
    return model_setup_summary()
