from __future__ import annotations

import hashlib
import json
from pathlib import Path

from platformdirs import user_data_dir

from .contextual_translation import (
    context_budget_for_duration,
    install_llama_cpp,
    llama_cpp_status,
)
from .dependencies import shared_huggingface_cache
from .media import DubLocalError


QUALITY_CONTEXT_MODEL = {
    "id": "qwen3-8b-q4-k-m",
    "label": "Qwen3 8B Q4_K_M · high quality",
    "repo_id": "Qwen/Qwen3-8B-GGUF",
    "revision": "6a569868d07d3bd59e8b97fb001bf8c0b254bb20",
    "filename": "Qwen3-8B-Q4_K_M.gguf",
    "sha256": "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785",
    "size": "5.03 GB",
    "license": "Apache-2.0",
    "native_context": 32768,
}

_REGISTRATION = ".dublocal-contextual-quality.json"


def quality_models_dir() -> Path:
    root = Path(user_data_dir("DubLocal")) / "models" / "contextual-translation"
    root.mkdir(parents=True, exist_ok=True)
    return root


def quality_contextual_model_path() -> Path:
    return quality_models_dir() / str(QUALITY_CONTEXT_MODEL["filename"])


def _registration_path() -> Path:
    return quality_models_dir() / _REGISTRATION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quality_registered_model_valid() -> bool:
    path = quality_contextual_model_path()
    marker = _registration_path()
    if not (path.exists() or path.is_symlink()) or not marker.is_file():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("repo_id") == QUALITY_CONTEXT_MODEL["repo_id"]
        and payload.get("revision") == QUALITY_CONTEXT_MODEL["revision"]
        and payload.get("sha256") == QUALITY_CONTEXT_MODEL["sha256"]
        and path.is_file()
    )


def install_quality_contextual_model() -> Path:
    destination = quality_contextual_model_path()
    if quality_registered_model_valid():
        return destination

    destination.unlink(missing_ok=True)
    _registration_path().unlink(missing_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise DubLocalError(
            "The Hugging Face download helper is missing from DubLocal. Run Repair installation once, then retry."
        ) from exc

    try:
        shared = Path(
            hf_hub_download(
                repo_id=str(QUALITY_CONTEXT_MODEL["repo_id"]),
                revision=str(QUALITY_CONTEXT_MODEL["revision"]),
                filename=str(QUALITY_CONTEXT_MODEL["filename"]),
                cache_dir=str(shared_huggingface_cache()),
            )
        ).resolve()
    except Exception as exc:
        raise DubLocalError(f"High-quality contextual translation model download failed: {exc}") from exc

    if _sha256(shared) != QUALITY_CONTEXT_MODEL["sha256"]:
        raise DubLocalError(
            "Downloaded Qwen3 8B model failed SHA-256 verification. DubLocal refused to register it."
        )

    try:
        destination.symlink_to(shared)
    except OSError as exc:
        raise DubLocalError(f"Could not link the shared Qwen3 8B model into DubLocal: {exc}") from exc

    _registration_path().write_text(
        json.dumps(
            {
                "repo_id": QUALITY_CONTEXT_MODEL["repo_id"],
                "revision": QUALITY_CONTEXT_MODEL["revision"],
                "filename": QUALITY_CONTEXT_MODEL["filename"],
                "sha256": QUALITY_CONTEXT_MODEL["sha256"],
                "shared_path": str(shared),
                "storage": "huggingface-shared-cache",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def remove_quality_contextual_model() -> bool:
    path = quality_contextual_model_path()
    marker = _registration_path()
    existed = path.exists() or path.is_symlink() or marker.exists()
    path.unlink(missing_ok=True)
    marker.unlink(missing_ok=True)
    return existed


def prepare_quality_contextual_translation() -> str:
    command = install_llama_cpp()
    model = install_quality_contextual_model()
    return f"{' '.join(command)} · {model.name}"


def quality_contextual_translation_status(
    source_language: str = "auto",
    target_language: str = "en",
    duration_ms: int | None = None,
) -> str:
    duration = max(0, int(duration_ms or 0))
    budget = context_budget_for_duration(duration)
    state = "installed" if quality_registered_model_valid() else "not installed"
    return (
        "```text\n"
        f"[engine] llama.cpp · {llama_cpp_status()}\n"
        f"[model] {QUALITY_CONTEXT_MODEL['label']} · {state} · {QUALITY_CONTEXT_MODEL['size']} · {QUALITY_CONTEXT_MODEL['license']}\n"
        f"[route] {source_language} → {target_language}\n"
        f"[context] {budget} token input budget · grows with media duration · native context {QUALITY_CONTEXT_MODEL['native_context']}\n"
        f"[shared cache] {shared_huggingface_cache()}\n"
        "[quality] Best mode adds a second context-aware review pass; Balanced mode skips it\n"
        "[policy] local-only; no cloud fallback\n"
        "```"
    )
