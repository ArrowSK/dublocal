from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from platformdirs import user_data_dir

from .dependencies import PythonRuntime, discover_python_runtime
from .media import DubLocalError


_RUSSIAN_MODULES = ("kokoro", "numpy", "torch", "huggingface_hub", "ruaccent")
_MIN_PYTHON = (3, 10)
_MAX_PYTHON = (3, 13)
_RUNTIME_NAME = "kokoro-ru-py312"


def _runtime_root() -> Path:
    return Path(user_data_dir("DubLocal")) / "runtimes" / _RUNTIME_NAME


def _runtime_python() -> Path:
    root = _runtime_root()
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _probe_python_version(python: Path) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [str(python), "-c", "import json,sys; print(json.dumps(list(sys.version_info[:2])))"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        major, minor = json.loads(result.stdout.strip().splitlines()[-1])
        return int(major), int(minor)
    except (IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _supported_python(python: Path) -> bool:
    version = _probe_python_version(python)
    return version is not None and _MIN_PYTHON <= version < _MAX_PYTHON


def _probe_modules(python: Path, modules: Iterable[str]) -> tuple[str, ...] | None:
    requested = tuple(dict.fromkeys(str(item) for item in modules if item))
    script = (
        "import importlib.util, json; "
        f"mods={requested!r}; "
        "print(json.dumps([m for m in mods if importlib.util.find_spec(m) is not None]))"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", script],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        return tuple(json.loads(result.stdout.strip().splitlines()[-1]))
    except (IndexError, TypeError, json.JSONDecodeError):
        return None


def _runtime_from_python(python: Path, label: str) -> PythonRuntime | None:
    if not python.is_file() or not _supported_python(python):
        return None
    found = _probe_modules(python, _RUSSIAN_MODULES)
    if found is None or set(found) != set(_RUSSIAN_MODULES):
        return None
    return PythonRuntime(python=python, label=label, modules=found)


def russian_runtime() -> PythonRuntime | None:
    dedicated = _runtime_from_python(_runtime_python(), "DubLocal Russian TTS runtime")
    if dedicated is not None:
        return dedicated

    reusable = discover_python_runtime(_RUSSIAN_MODULES, allow_current=True)
    if reusable is not None and _supported_python(reusable.python):
        return reusable
    return None


def _brew_path() -> str | None:
    found = shutil.which("brew")
    if found:
        return found
    for path in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(path).is_file():
            return path
    return None


def _base_python_candidates() -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("DUBLOCAL_TTS_PYTHON", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())

    if _MIN_PYTHON <= sys.version_info[:2] < _MAX_PYTHON:
        candidates.append(Path(sys.executable))

    for command in ("python3.12", "python3.11"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))

    for path in (
        "/opt/homebrew/bin/python3.12",
        "/usr/local/bin/python3.12",
        "/opt/homebrew/bin/python3.11",
        "/usr/local/bin/python3.11",
    ):
        candidates.append(Path(path))

    seen: set[str] = set()
    result: list[Path] = []
    for candidate in candidates:
        key = os.path.abspath(os.path.expanduser(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        path = Path(key)
        if path.is_file() and _supported_python(path):
            result.append(path)
    return result


def _ensure_base_python() -> Path:
    candidates = _base_python_candidates()
    if candidates:
        return candidates[0]

    brew = _brew_path()
    if brew and sys.platform == "darwin":
        try:
            subprocess.run(
                [brew, "install", "python@3.12"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30 * 60,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
            raise DubLocalError(
                "Russian TTS needs Python 3.11 or 3.12 because Kokoro 0.9.x does not support Python 3.13. "
                f"DubLocal could not prepare Python 3.12 with Homebrew: {detail}"
            ) from exc
        candidates = _base_python_candidates()
        if candidates:
            return candidates[0]

    raise DubLocalError(
        "Russian TTS needs Python 3.11 or 3.12 because Kokoro 0.9.x does not support Python 3.13. "
        "Install Python 3.12 (Homebrew: brew install python@3.12), restart DubLocal, and click Prepare again."
    )


def _install_runtime(base_python: Path) -> PythonRuntime:
    root = _runtime_root()
    python = _runtime_python()
    root.parent.mkdir(parents=True, exist_ok=True)

    if python.exists() and not _supported_python(python):
        shutil.rmtree(root, ignore_errors=True)

    if not python.is_file():
        try:
            subprocess.run(
                [str(base_python), "-m", "venv", str(root)],
                capture_output=True,
                text=True,
                check=True,
                timeout=5 * 60,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
            raise DubLocalError(f"Could not create the isolated Russian TTS Python runtime: {detail}") from exc

    requirements = (
        "kokoro>=0.9.4,<1.0",
        "huggingface-hub>=1.0,<2.0",
        "ruaccent>=1.5.6,<2.0",
    )
    try:
        subprocess.run(
            [str(python), "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10 * 60,
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", *requirements],
            capture_output=True,
            text=True,
            check=True,
            timeout=30 * 60,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
        raise DubLocalError(f"Could not install the optional Russian TTS runtime: {detail}") from exc

    runtime = _runtime_from_python(python, "DubLocal Russian TTS runtime")
    if runtime is None:
        raise DubLocalError(
            "Russian TTS packages finished installing, but the isolated Python 3.11/3.12 runtime did not validate."
        )
    return runtime


def prepare_russian_runtime() -> PythonRuntime:
    runtime = russian_runtime()
    if runtime is None:
        runtime = _install_runtime(_ensure_base_python())

    # Keep the existing legal/packaging boundary: eSpeak NG remains an external
    # executable and is prepared by the established provider helper.
    from . import tts_provider_refinement as provider_refinement

    provider_refinement._ensure_espeak_ng()
    return runtime


def install_russian_runtime_compat(provider_refinement_module) -> None:
    """Install the Python-version-safe Russian runtime hooks before provider routing."""

    provider_refinement_module._russian_runtime = russian_runtime
    provider_refinement_module._prepare_russian_runtime = prepare_russian_runtime
