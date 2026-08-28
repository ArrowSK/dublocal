from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from platformdirs import user_cache_dir

from .dependencies import PythonRuntime, discover_python_runtime
from .hardware_profile import HardwareProfile, detect_hardware_profile, hardware_summary
from .media import DubLocalError


ProgressCallback = Callable[[float, str], None]
DEMUCS_MODULES = ("demucs", "torch", "torchaudio")
MANAGED_RUNTIME_PACKAGES = (
    "demucs==4.0.1",
    "torch>=2.2,<2.7",
    "torchaudio>=2.2,<2.7",
)


@dataclass(frozen=True, slots=True)
class SeparationProfile:
    tier: str
    label: str
    model: str
    segment_seconds: float
    device: str
    explanation: str


@dataclass(frozen=True, slots=True)
class SeparationResult:
    vocals: Path
    accompaniment: Path
    model: str
    device: str
    runtime_label: str
    profile_label: str


def _managed_runtime_root() -> Path:
    return Path(user_cache_dir("DubLocal")) / "runtimes" / "demucs"


def _managed_python() -> Path:
    return _managed_runtime_root() / "bin" / "python"


def _probe_runtime(python: Path, label: str) -> PythonRuntime | None:
    if not python.is_file() or not os.access(python, os.X_OK):
        return None
    script = (
        "import importlib.util, json; "
        f"mods={DEMUCS_MODULES!r}; "
        "print(json.dumps([m for m in mods if importlib.util.find_spec(m) is not None]))"
    )
    try:
        completed = subprocess.run(
            [str(python), "-c", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        found = tuple(json.loads(completed.stdout.strip().splitlines()[-1]))
    except (IndexError, TypeError, json.JSONDecodeError):
        return None
    if set(found) != set(DEMUCS_MODULES):
        return None
    return PythonRuntime(python=python, label=label, modules=found)


def separation_runtime() -> PythonRuntime | None:
    managed = _probe_runtime(_managed_python(), "DubLocal managed Demucs runtime")
    if managed is not None:
        return managed
    return discover_python_runtime(DEMUCS_MODULES, allow_current=True)


def recommend_separation_profile(
    profile: HardwareProfile | None = None,
) -> SeparationProfile:
    """Choose a conservative Demucs profile that remains usable across Apple Silicon.

    macOS CPU inference is the compatibility baseline documented by Demucs. Segment
    length, not an assumption about a particular M-generation, is used to control
    memory pressure. Higher-memory Macs may use the fine-tuned ensemble; 8 GB Macs
    stay on the single htdemucs model with shorter chunks.
    """

    hardware = profile or detect_hardware_profile()
    memory = hardware.memory_gib
    memory_text = f"{memory:.0f} GB" if memory is not None else "unknown RAM"

    if hardware.apple_silicon and memory is not None and memory < 12:
        return SeparationProfile(
            tier="light",
            label="Low-memory Apple Silicon",
            model="htdemucs",
            segment_seconds=4.0,
            device="cpu",
            explanation=(
                f"{memory_text} Apple Silicon → htdemucs in 4 s chunks on CPU. "
                "This prioritizes unified-memory stability over separation speed."
            ),
        )

    if hardware.apple_silicon and memory is not None and memory >= 32:
        return SeparationProfile(
            tier="quality",
            label="High-memory Apple Silicon",
            model="htdemucs_ft",
            segment_seconds=7.5,
            device="cpu",
            explanation=(
                f"{memory_text} Apple Silicon → fine-tuned htdemucs ensemble in 7.5 s chunks. "
                "It is substantially slower but improves vocal isolation on capable Macs."
            ),
        )

    if hardware.apple_silicon:
        return SeparationProfile(
            tier="balanced",
            label="Apple Silicon",
            model="htdemucs",
            segment_seconds=7.0,
            device="cpu",
            explanation=(
                f"{memory_text} Apple Silicon → htdemucs in 7 s chunks on the documented CPU path. "
                "This avoids relying on MPS operator coverage for a feature that must work on every M-series Mac."
            ),
        )

    # DubLocal remains Mac-first, but keeping a CPU profile makes tests and Intel Macs
    # fail gracefully rather than baking Apple-Silicon-only assumptions into the mixer.
    return SeparationProfile(
        tier="compatibility",
        label="CPU compatibility",
        model="htdemucs",
        segment_seconds=4.0,
        device="cpu",
        explanation=(
            f"{hardware_summary(hardware)} → conservative htdemucs CPU profile because this host is not classified as Apple Silicon."
        ),
    )


def separation_status(profile: HardwareProfile | None = None) -> str:
    recommendation = recommend_separation_profile(profile)
    runtime = separation_runtime()
    runtime_text = (
        f"ready · {runtime.label} · {runtime.python}"
        if runtime is not None
        else "not prepared · lightweight dialogue mixing remains available"
    )
    return (
        "```text\n"
        f"[vocal separation] {runtime_text}\n"
        f"[recommended] {recommendation.model} · {recommendation.segment_seconds:.1f}s chunks · {recommendation.device}\n"
        f"[why] {recommendation.explanation}\n"
        "[policy] separation is optional; Simple mode never needs it to complete a dub\n"
        "```"
    )


def prepare_separation_runtime() -> str:
    """Prepare an isolated Demucs runtime without altering another app's environment."""

    existing = separation_runtime()
    if existing is not None:
        return f"{existing.label} · already ready"

    root = _managed_runtime_root()
    python = _managed_python()
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not python.is_file():
            venv.EnvBuilder(with_pip=True, clear=False, symlinks=True).create(root)
        completed = subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                *MANAGED_RUNTIME_PACKAGES,
            ],
            capture_output=True,
            text=True,
            timeout=30 * 60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DubLocalError(f"Could not prepare the isolated vocal-separation runtime: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "pip failed").strip()
        raise DubLocalError(f"Could not prepare the isolated vocal-separation runtime: {detail}")

    runtime = _probe_runtime(python, "DubLocal managed Demucs runtime")
    if runtime is None:
        raise DubLocalError(
            "Demucs installation completed, but DubLocal could not validate the isolated runtime."
        )
    return f"{runtime.label} · ready"


def _notify(callback: ProgressCallback | None, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), label)


def separate_vocals(
    source_media: str | Path,
    output_dir: Path,
    *,
    profile: SeparationProfile | None = None,
    prepare_if_missing: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> SeparationResult:
    source = Path(source_media).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("The source media for vocal separation no longer exists.")

    runtime = separation_runtime()
    if runtime is None and prepare_if_missing:
        _notify(progress_callback, 0.02, "Preparing isolated vocal-separation runtime")
        prepare_separation_runtime()
        runtime = separation_runtime()
    if runtime is None:
        raise DubLocalError(
            "Vocal separation is not prepared. Use Advanced → Audio mix → Prepare vocal separation, "
            "or keep Auto/Dialogue mixing."
        )

    recommendation = profile or recommend_separation_profile()
    separation_root = output_dir / "separated"
    separation_root.mkdir(parents=True, exist_ok=True)
    _notify(
        progress_callback,
        0.05,
        f"Separating vocals · {recommendation.model} · {recommendation.label}",
    )

    command = [
        str(runtime.python),
        "-m",
        "demucs",
        "--two-stems",
        "vocals",
        "-n",
        recommendation.model,
        "-d",
        recommendation.device,
        "--segment",
        f"{recommendation.segment_seconds:.1f}",
        "--out",
        str(separation_root),
        str(source),
    ]
    env = os.environ.copy()
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=6 * 60 * 60,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DubLocalError(f"Vocal separation failed: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Demucs failed").strip()
        raise DubLocalError(f"Vocal separation failed: {detail}")

    model_root = separation_root / recommendation.model
    candidates = [path for path in model_root.iterdir() if path.is_dir()] if model_root.is_dir() else []
    if not candidates:
        raise DubLocalError("Demucs completed without creating a separated-track folder.")
    # One source is passed per invocation. Resolve by stem names instead of relying on
    # filename sanitization rules that can vary across Demucs releases.
    track_root = candidates[0]
    vocals = track_root / "vocals.wav"
    accompaniment = track_root / "no_vocals.wav"
    if not vocals.is_file() or not accompaniment.is_file():
        raise DubLocalError("Demucs completed, but the expected vocals/no_vocals stems are missing.")

    _notify(progress_callback, 1.0, "Vocal and accompaniment stems ready")
    return SeparationResult(
        vocals=vocals,
        accompaniment=accompaniment,
        model=recommendation.model,
        device=recommendation.device,
        runtime_label=runtime.label,
        profile_label=recommendation.label,
    )
