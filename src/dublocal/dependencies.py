from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PythonRuntime:
    python: Path
    label: str
    modules: tuple[str, ...]


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _python_from_entrypoint(name: str) -> Path | None:
    """Resolve the Python interpreter behind a console script when possible."""

    executable = shutil.which(name)
    if not executable:
        return None
    path = Path(executable)
    try:
        with path.open("rb") as handle:
            first = handle.readline(1024).decode("utf-8", errors="ignore").strip()
    except OSError:
        return None
    if not first.startswith("#!"):
        return None
    raw = first[2:].strip()
    # `#!/path/to/python` is the useful virtualenv case. `/usr/bin/env python`
    # does not identify a separate environment and is therefore ignored.
    if not raw or raw.startswith("/usr/bin/env ") or " " in raw:
        return None
    candidate = Path(raw).expanduser()
    return candidate if candidate.is_file() else None


def _candidate_pythons() -> list[tuple[Path, str]]:
    root = _repository_root()
    home = Path.home()
    candidates: list[tuple[Path, str]] = [(Path(sys.executable), "DubLocal environment")]

    configured = os.environ.get("DUBLOCAL_EXTERNAL_PYTHONS", "")
    for raw in configured.split(os.pathsep):
        value = raw.strip()
        if value:
            candidates.append((Path(value).expanduser(), "Configured external runtime"))

    names = (
        "narroam-studio",
        "NarRoam-Studio",
        "NarRoam Studio",
        "kokoroo",
        "Kokoroo",
        "kokoro",
        "Kokoro",
        "chatterbox",
        "Chatterbox",
    )
    parents = (
        root.parent,
        home,
        home / "Developer",
        home / "Projects",
        home / "Documents",
        home / "Code",
        home / "src",
        home / ".virtualenvs",
        home / ".venvs",
        home / "venvs",
    )
    for parent in parents:
        for name in names:
            base = parent / name
            candidates.append((base / ".venv" / "bin" / "python", base.name))
            candidates.append((base / "venv" / "bin" / "python", base.name))
            # Named venv roots such as ~/.venvs/kokoro already are the venv.
            candidates.append((base / "bin" / "python", base.name))

    pipx = home / ".local" / "pipx" / "venvs"
    for name in ("kokoro", "kokoro-tts", "kokoroo", "chatterbox"):
        candidates.append((pipx / name / "bin" / "python", f"pipx:{name}"))

    for command in ("kokoro", "kokoroo", "chatterbox"):
        python = _python_from_entrypoint(command)
        if python:
            candidates.append((python, f"{command} console environment"))

    seen: set[Path] = set()
    result: list[tuple[Path, str]] = []
    for path, label in candidates:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file() or not os.access(resolved, os.X_OK):
            continue
        seen.add(resolved)
        result.append((resolved, label))
    return result


def _probe_python(python: Path, modules: Iterable[str]) -> tuple[str, ...] | None:
    requested = tuple(dict.fromkeys(str(item) for item in modules if item))
    script = (
        "import importlib.util, json; "
        f"mods={requested!r}; "
        "found=[m for m in mods if importlib.util.find_spec(m) is not None]; "
        "print(json.dumps(found))"
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
        found = tuple(json.loads(result.stdout.strip().splitlines()[-1]))
    except (IndexError, json.JSONDecodeError, TypeError):
        return None
    return found


def discover_python_runtime(
    required_modules: Iterable[str],
    *,
    allow_current: bool = True,
) -> PythonRuntime | None:
    required = tuple(dict.fromkeys(str(item) for item in required_modules if item))
    current = Path(sys.executable).resolve()
    for python, label in _candidate_pythons():
        if not allow_current and python == current:
            continue
        found = _probe_python(python, required)
        if found is None or set(found) != set(required):
            continue
        return PythonRuntime(python=python, label=label, modules=found)
    return None


def preferred_python_for(required_modules: Iterable[str]) -> PythonRuntime | None:
    """Return a compatible existing Python runtime without modifying it.

    Backends that support an external-process bridge can use this runtime rather
    than reinstalling the same heavy Python stack into DubLocal's own venv.
    """

    return discover_python_runtime(required_modules, allow_current=True)


def shared_huggingface_cache() -> Path:
    explicit = os.environ.get("HF_HUB_CACHE")
    if explicit:
        return Path(explicit).expanduser()
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser() / "hub"
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "huggingface" / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def local_resource_status() -> str:
    lines: list[str] = []

    for executable in ("ffmpeg", "ffprobe", "whisper-cli"):
        resolved = shutil.which(executable)
        state = resolved or "not found"
        lines.append(f"[{executable}] {state}")

    hf_cache = shared_huggingface_cache()
    cache_state = "available" if hf_cache.exists() else "will be created on first Hugging Face model use"
    lines.append(f"[huggingface cache] {cache_state} · {hf_cache}")

    kokoro = discover_python_runtime(("kokoro",), allow_current=True)
    if kokoro:
        location = (
            "current DubLocal venv"
            if kokoro.python.resolve() == Path(sys.executable).resolve()
            else f"{kokoro.label} · {kokoro.python}"
        )
        lines.append(f"[kokoro] reusable runtime detected · {location}")
    else:
        lines.append("[kokoro] no reusable Python runtime detected yet · M4 can install or link one later")

    lines.append(
        "[policy] reuse existing executables, shared model caches and compatible external runtimes when safe"
    )
    lines.append(
        "[isolation] Python packages from another venv are never injected into DubLocal's interpreter; backends reuse them through a separate-process bridge"
    )
    return "```text\n" + "\n".join(lines) + "\n```"
