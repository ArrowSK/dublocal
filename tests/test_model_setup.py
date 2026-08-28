from __future__ import annotations

from pathlib import Path

import dublocal.model_setup as model_setup
from dublocal.hardware_profile import HardwareProfile


def _profile(*, architecture: str, memory_gib: int, system: str = "Darwin") -> HardwareProfile:
    return HardwareProfile(
        architecture=architecture,
        memory_bytes=memory_gib * 1024**3,
        cpu_name="Test Mac",
        system_name=system,
    )


def test_apple_silicon_gets_accurate_whisper_and_light_translation_on_8gb() -> None:
    recommendation = model_setup.recommended_model_setup(
        _profile(architecture="arm64", memory_gib=8)
    )

    assert recommendation.whisper_model_id == "large-v3-turbo-q5_0"
    assert recommendation.translation_model_key == "4b"
    assert recommendation.approximate_model_gb > 3.0


def test_intel_gets_conservative_whisper_default() -> None:
    recommendation = model_setup.recommended_model_setup(
        _profile(architecture="x86_64", memory_gib=16)
    )

    assert recommendation.whisper_model_id == "base"
    assert recommendation.translation_model_key == "4b"


def test_skip_marks_first_run_seen(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "model-setup.json"
    monkeypatch.setattr(model_setup, "setup_state_path", lambda: state_path)

    assert model_setup._read_state() == {}
    model_setup.mark_first_run_skipped()

    payload = model_setup._read_state()
    assert payload["first_run_seen"] is True
    assert payload["skipped"] is True


def test_prepare_recommended_models_runs_one_sequential_setup(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "model-setup.json"
    monkeypatch.setattr(model_setup, "setup_state_path", lambda: state_path)

    recommendation = model_setup.recommended_model_setup(
        _profile(architecture="arm64", memory_gib=8)
    )
    monkeypatch.setattr(model_setup, "recommended_model_setup", lambda profile=None: recommendation)

    calls: list[str] = []

    def install_whisper(model_id: str, *, progress_callback=None):
        calls.append(f"whisper:{model_id}")
        if progress_callback:
            progress_callback(0.5, "Downloading Whisper model")
            progress_callback(1.0, "Whisper model ready")
        return tmp_path / "whisper.bin"

    monkeypatch.setattr(model_setup, "install_whisper_model_with_progress", install_whisper)
    monkeypatch.setattr(model_setup, "install_llama_cpp", lambda: calls.append("llama") or ["llama-cli"])
    monkeypatch.setattr(
        model_setup,
        "install_contextual_model_for",
        lambda key: calls.append(f"translation:{key}") or (tmp_path / "qwen.gguf"),
    )
    monkeypatch.setattr(model_setup, "kokoro_default_voice", lambda language: "af_heart")
    monkeypatch.setattr(
        model_setup,
        "prepare_kokoro",
        lambda language, voice, speed: calls.append(f"kokoro:{language}:{voice}") or "ready",
    )
    monkeypatch.setattr(model_setup, "model_setup_summary", lambda profile=None: "READY")

    progress: list[tuple[float, str]] = []
    result = model_setup.prepare_recommended_models(
        progress_callback=lambda value, label: progress.append((value, label))
    )

    assert result == "READY"
    assert calls == [
        "whisper:large-v3-turbo-q5_0",
        "llama",
        "translation:4b",
        "kokoro:en-US:af_heart",
    ]
    assert progress[-1][0] == 1.0
    payload = model_setup._read_state()
    assert payload["first_run_seen"] is True
    assert payload["voice_prepared"] is True
