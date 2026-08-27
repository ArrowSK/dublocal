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


def _identity_path(path: Path) -> Path:
    """Return an absolute path without resolving virtualenv symlinks.

    On macOS, ``venv/bin/python`` is commonly a symlink to the same framework
    interpreter used by several environments. Resolving that symlink erases the
    virtualenv identity and makes two different environments look identical.
    Executing the symlink path itself is what activates the correct venv prefix,
    so discovery must preserve it.
    """

    return Path(os.path.abspath(os.path.expanduser(str(path))))


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
    if not raw or raw.startswith("/usr/bin/env ") or " " in raw:
        return None
    candidate = _identity_path(Path(raw))
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
        identity = _identity_path(path)
        if identity in seen or not identity.is_file() or not os.access(identity, os.X_OK):
            continue
        seen.add(identity)
        result.append((identity, label))
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
    current = _identity_path(Path(sys.executable))
    for python, label in _candidate_pythons():
        if not allow_current and _identity_path(python) == current:
            continue
        found = _probe_python(python, required)
        if found is None or set(found) != set(required):
            continue
        return PythonRuntime(python=_identity_path(python), label=label, modules=found)
    return None


def preferred_python_for(required_modules: Iterable[str]) -> PythonRuntime | None:
    """Return a compatible existing Python runtime without modifying it."""

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


def _llama_resource() -> str:
    cli = shutil.which("llama-cli")
    if cli:
        return cli
    llama = shutil.which("llama")
    if llama:
        return f"{llama} cli"
    for candidate in ("/opt/homebrew/bin/llama-cli", "/usr/local/bin/llama-cli"):
        if Path(candidate).is_file():
            return candidate
    return "not found"


def local_resource_status() -> str:
    lines: list[str] = []

    for executable in ("ffmpeg", "ffprobe", "whisper-cli"):
        resolved = shutil.which(executable)
        state = resolved or "not found"
        lines.append(f"[{executable}] {state}")
    lines.append(f"[llama.cpp] {_llama_resource()}")

    hf_cache = shared_huggingface_cache()
    cache_state = "available" if hf_cache.exists() else "will be created on first Hugging Face model use"
    lines.append(f"[huggingface cache] {cache_state} · {hf_cache}")

    kokoro = discover_python_runtime(
        ("kokoro", "numpy", "torch", "huggingface_hub"), allow_current=True
    )
    if kokoro:
        current = _identity_path(Path(sys.executable))
        location = (
            "current DubLocal venv"
            if _identity_path(kokoro.python) == current
            else f"{kokoro.label} · {kokoro.python}"
        )
        lines.append(f"[kokoro] reusable runtime detected · {location}")
    else:
        lines.append("[kokoro] no compatible reusable runtime detected · Settings → Model Manager can prepare one")

    lines.append(
        "[policy] reuse existing executables, shared model caches and compatible external runtimes when safe"
    )
    lines.append(
        "[isolation] Python packages from another venv are never injected into DubLocal's interpreter; backends reuse them through a separate-process bridge"
    )
    return "```text\n" + "\n".join(lines) + "\n```"
