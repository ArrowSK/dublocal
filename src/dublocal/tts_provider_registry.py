from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from huggingface_hub import model_info, snapshot_download
from platformdirs import user_config_dir, user_data_dir

from .media import DubLocalError


_SCHEMA_VERSION = 1
_ALLOWED_FRONTENDS = {
    "russian-v2",
    "official-a",
    "official-b",
    "official-e",
    "official-f",
    "official-h",
    "official-i",
    "official-j",
    "official-p",
    "official-z",
}
_FORBIDDEN_KEYS = {
    "code",
    "command",
    "entrypoint",
    "module",
    "python",
    "script",
    "shell",
}
_TOP_LEVEL_KEYS = {
    "schema_version",
    "id",
    "label",
    "language",
    "language_label",
    "backend",
    "frontend",
    "source",
    "license",
    "config_file",
    "voices",
    "default_voice",
    "preferred",
    "notes",
    "required_patterns",
}
_VOICE_KEYS = {"id", "label", "gender", "model_file", "voice_file"}
_SOURCE_KEYS = {"type", "repo_id", "revision", "path"}
_LICENSE_KEYS = {"id", "commercial_use", "redistribution", "source", "attribution"}
_PROVIDER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_REVISION_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


BUILTIN_RUSSIAN_PROVIDER: dict[str, Any] = {
    "schema_version": 1,
    "id": "kokoro-ru-v2-vetted",
    "label": "Kokoro-RU v2 · vetted third-party",
    "language": "ru",
    "language_label": "Russian",
    "backend": "kokoro-local",
    "frontend": "russian-v2",
    # Pin a known snapshot rather than following mutable main. The resolved full
    # commit is recorded in the local install receipt when the provider is prepared.
    "source": {
        "type": "huggingface",
        "repo_id": "zaakirio/kokoro-ru",
        "revision": "9da785e",
    },
    "license": {
        "id": "OpenRAIL",
        "commercial_use": True,
        "redistribution": "not-bundled",
        "source": "https://huggingface.co/zaakirio/kokoro-ru",
        "attribution": "zaakirio/kokoro-ru; Dialogs Russian speech corpus; Kokoro-82M",
    },
    "config_file": "kokoro-config.json",
    "voices": [
        {
            "id": "rf_sveta",
            "label": "Sveta · female · third-party",
            "gender": "female",
            "model_file": "kokoro-ru-v2-base.pth",
            "voice_file": "voices/sveta.pt",
        },
        {
            "id": "rf_masha",
            "label": "Masha · female · third-party",
            "gender": "female",
            "model_file": "kokoro-ru-v2-base.pth",
            "voice_file": "voices/masha.pt",
        },
        {
            "id": "rm_dima",
            "label": "Dima · male · third-party",
            "gender": "male",
            "model_file": "kokoro-ru-v2-dima.pth",
            "voice_file": "voices/dima.pt",
        },
    ],
    "default_voice": "rf_sveta",
    "preferred": True,
    "required_patterns": [
        "README.md",
        "kokoro-config.json",
        "kokoro-ru-v2-base.pth",
        "kokoro-ru-v2-dima.pth",
        "voices/sveta.pt",
        "voices/masha.pt",
        "voices/dima.pt",
        "espeak-data/**",
    ],
    "notes": "Persistent local snapshot; generation does not contact the model fork after preparation.",
}


@dataclass(frozen=True, slots=True)
class TTSProvider:
    manifest: dict[str, Any]
    builtin: bool = False

    @property
    def id(self) -> str:
        return str(self.manifest["id"])

    @property
    def language(self) -> str:
        return str(self.manifest["language"])

    @property
    def label(self) -> str:
        return str(self.manifest["label"])

    @property
    def install_dir(self) -> Path:
        return provider_install_root() / self.id

    @property
    def receipt_path(self) -> Path:
        return self.install_dir / "install-receipt.json"

    @property
    def voices(self) -> list[dict[str, str]]:
        return [dict(item) for item in self.manifest.get("voices", [])]


def provider_install_root() -> Path:
    path = Path(user_data_dir("DubLocal")) / "tts-providers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def provider_config_root() -> Path:
    path = Path(user_config_dir("DubLocal")) / "tts-providers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_relative(value: str, field: str) -> str:
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts or not str(value).strip():
        raise DubLocalError(f"Custom TTS provider {field} must be a safe relative path.")
    return path.as_posix()


def _selection_prefix(frontend: str) -> str:
    return "r" if frontend == "russian-v2" else frontend.rsplit("-", 1)[-1]


def validate_provider_manifest(raw: dict[str, Any], *, builtin: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DubLocalError("TTS provider manifest must be a JSON object.")
    forbidden = _FORBIDDEN_KEYS.intersection(raw)
    if forbidden:
        raise DubLocalError(
            "Custom TTS providers are data-only; executable fields are not allowed: "
            + ", ".join(sorted(forbidden))
        )
    unknown = set(raw) - _TOP_LEVEL_KEYS
    if unknown:
        raise DubLocalError("Unknown TTS provider fields: " + ", ".join(sorted(unknown)))
    if int(raw.get("schema_version") or 0) != _SCHEMA_VERSION:
        raise DubLocalError(f"TTS provider schema_version must be {_SCHEMA_VERSION}.")

    provider_id = str(raw.get("id") or "")
    if not _PROVIDER_ID_RE.fullmatch(provider_id):
        raise DubLocalError("TTS provider id must be 2-64 lowercase letters/numbers/._- characters.")
    if str(raw.get("backend") or "") != "kokoro-local":
        raise DubLocalError("Only the audited kokoro-local custom backend is currently supported.")
    frontend = str(raw.get("frontend") or "")
    if frontend not in _ALLOWED_FRONTENDS:
        raise DubLocalError("Unsupported TTS frontend. Custom executable frontends are intentionally not allowed.")

    language = str(raw.get("language") or "").strip().replace("_", "-")
    if not language:
        raise DubLocalError("TTS provider language is required.")
    language_label = str(raw.get("language_label") or language).strip()
    label = str(raw.get("label") or provider_id).strip()

    source = raw.get("source")
    if not isinstance(source, dict) or set(source) - _SOURCE_KEYS:
        raise DubLocalError("TTS provider source must contain only type/repo_id/revision/path.")
    source_type = str(source.get("type") or "")
    if source_type == "huggingface":
        repo_id = str(source.get("repo_id") or "")
        revision = str(source.get("revision") or "")
        if "/" not in repo_id or not repo_id.strip("/"):
            raise DubLocalError("Hugging Face TTS provider requires owner/repository repo_id.")
        if not _REVISION_RE.fullmatch(revision):
            raise DubLocalError(
                "Remote custom TTS providers must pin an immutable 7-40 character hex revision; mutable main/tags are rejected."
            )
        normalized_source = {"type": "huggingface", "repo_id": repo_id, "revision": revision}
    elif source_type == "local":
        local = Path(str(source.get("path") or "")).expanduser()
        if not local.is_dir():
            raise DubLocalError("Local TTS provider source path must be an existing directory.")
        normalized_source = {"type": "local", "path": str(local.resolve())}
    else:
        raise DubLocalError("TTS provider source type must be huggingface or local.")

    licence = raw.get("license")
    if not isinstance(licence, dict) or set(licence) - _LICENSE_KEYS:
        raise DubLocalError("TTS provider license metadata is required and must use the documented fields.")
    if not str(licence.get("id") or "").strip():
        raise DubLocalError("TTS provider license.id is required.")
    if "commercial_use" not in licence:
        raise DubLocalError("TTS provider license.commercial_use must be explicitly true or false.")

    config_file = _safe_relative(str(raw.get("config_file") or ""), "config_file")
    voices_raw = raw.get("voices")
    if not isinstance(voices_raw, list) or not voices_raw:
        raise DubLocalError("TTS provider must declare at least one voice.")
    prefix = _selection_prefix(frontend)
    voices: list[dict[str, str]] = []
    seen: set[str] = set()
    for voice in voices_raw:
        if not isinstance(voice, dict) or set(voice) - _VOICE_KEYS:
            raise DubLocalError("Each TTS voice must use id/label/gender/model_file/voice_file only.")
        voice_id = str(voice.get("id") or "")
        if not voice_id.startswith(prefix) or voice_id in seen:
            raise DubLocalError(
                f"Voice ids must be unique and start with {prefix!r} for frontend {frontend}."
            )
        seen.add(voice_id)
        voices.append(
            {
                "id": voice_id,
                "label": str(voice.get("label") or voice_id),
                "gender": str(voice.get("gender") or "unspecified"),
                "model_file": _safe_relative(str(voice.get("model_file") or ""), "model_file"),
                "voice_file": _safe_relative(str(voice.get("voice_file") or ""), "voice_file"),
            }
        )
    default_voice = str(raw.get("default_voice") or "")
    if default_voice not in seen:
        raise DubLocalError("TTS provider default_voice must match a declared voice id.")

    required = raw.get("required_patterns") or []
    if not isinstance(required, list):
        raise DubLocalError("required_patterns must be a JSON list.")
    required_patterns = [str(item) for item in required if str(item).strip()]
    if not required_patterns:
        required_patterns = [
            config_file,
            *sorted({item["model_file"] for item in voices}),
            *sorted({item["voice_file"] for item in voices}),
        ]

    return {
        "schema_version": _SCHEMA_VERSION,
        "id": provider_id,
        "label": label,
        "language": language,
        "language_label": language_label,
        "backend": "kokoro-local",
        "frontend": frontend,
        "source": normalized_source,
        "license": dict(licence),
        "config_file": config_file,
        "voices": voices,
        "default_voice": default_voice,
        "preferred": bool(raw.get("preferred", False)),
        "notes": str(raw.get("notes") or ""),
        "required_patterns": required_patterns,
        "builtin": bool(builtin),
    }


def _load_custom_manifests() -> list[TTSProvider]:
    providers: list[TTSProvider] = []
    for path in sorted(provider_config_root().glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            providers.append(TTSProvider(validate_provider_manifest(raw)))
        except Exception:
            # A broken user manifest must never prevent DubLocal from starting.
            continue
    return providers


def all_providers() -> list[TTSProvider]:
    builtin = TTSProvider(validate_provider_manifest(BUILTIN_RUSSIAN_PROVIDER, builtin=True), builtin=True)
    return [builtin, *_load_custom_manifests()]


def provider_is_installed(provider: TTSProvider) -> bool:
    if not provider.receipt_path.is_file():
        return False
    try:
        receipt = json.loads(provider.receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if receipt.get("provider_id") != provider.id:
        return False
    required = receipt.get("required_files") or []
    return bool(required) and all((provider.install_dir / str(item)).is_file() for item in required)


def provider_for_language(language: str, *, require_installed: bool = False) -> TTSProvider | None:
    normalized = str(language or "").replace("_", "-")
    candidates = [item for item in all_providers() if item.language == normalized]
    if require_installed:
        candidates = [item for item in candidates if provider_is_installed(item)]
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            0 if provider_is_installed(item) and item.manifest.get("preferred") and not item.builtin else 1,
            0 if provider_is_installed(item) and item.builtin else 1,
            0 if provider_is_installed(item) else 1,
            0 if item.manifest.get("preferred") else 1,
            0 if item.builtin else 1,
            item.id,
        )
    )
    return candidates[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_local_source(source: Path, destination: Path) -> str:
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return "local"


def _download_hf_source(provider: TTSProvider, destination: Path) -> str:
    source = provider.manifest["source"]
    repo_id = str(source["repo_id"])
    revision = str(source["revision"])
    try:
        resolved = str(model_info(repo_id, revision=revision).sha)
        snapshot_download(
            repo_id=repo_id,
            revision=resolved,
            allow_patterns=list(provider.manifest["required_patterns"]),
            local_dir=str(destination),
        )
    except Exception as exc:
        raise DubLocalError(
            f"Could not prepare {provider.label} from {repo_id}@{revision}. "
            "If the upstream source moved, register a compatible local or mirrored provider manifest. "
            f"Details: {exc}"
        ) from exc
    return resolved


def _required_files(provider: TTSProvider, root: Path) -> list[str]:
    files = {provider.manifest["config_file"]}
    for voice in provider.voices:
        files.add(voice["model_file"])
        files.add(voice["voice_file"])
    if provider.manifest["frontend"] == "russian-v2":
        # Russian quality depends on the acute-aware eSpeak data snapshot.
        data = root / "espeak-data"
        if not data.is_dir():
            raise DubLocalError("Russian provider is missing its acute-aware espeak-data directory.")
        files.update(path.relative_to(root).as_posix() for path in data.rglob("*") if path.is_file())
    missing = [item for item in sorted(files) if not (root / item).is_file()]
    if missing:
        raise DubLocalError("TTS provider snapshot is incomplete: " + ", ".join(missing[:8]))
    return sorted(files)


def prepare_provider(provider: TTSProvider) -> Path:
    # Once prepared, use the persistent local copy without consulting the upstream
    # source. This is the explicit resilience boundary for third-party forks.
    if provider_is_installed(provider):
        return provider.install_dir

    root = provider_install_root()
    staging = Path(tempfile.mkdtemp(prefix=f".{provider.id}-", dir=root))
    try:
        source = provider.manifest["source"]
        if source["type"] == "local":
            resolved = _copy_local_source(Path(str(source["path"])), staging)
        else:
            resolved = _download_hf_source(provider, staging)
        required = _required_files(provider, staging)
        hashes = {
            item: _sha256(staging / item)
            for item in required
            if (staging / item).stat().st_size <= 8 * 1024 * 1024
        }
        receipt = {
            "schema_version": _SCHEMA_VERSION,
            "provider_id": provider.id,
            "provider_manifest": provider.manifest,
            "resolved_revision": resolved,
            "required_files": required,
            "small_file_sha256": hashes,
        }
        (staging / "install-receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        final = provider.install_dir
        if final.exists():
            shutil.rmtree(final)
        staging.replace(final)
        return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def register_custom_provider(manifest_text: str) -> TTSProvider:
    try:
        raw = json.loads(str(manifest_text or ""))
    except json.JSONDecodeError as exc:
        raise DubLocalError(f"Custom TTS provider manifest is not valid JSON: {exc}") from exc
    manifest = validate_provider_manifest(raw)
    provider = TTSProvider(manifest)
    path = provider_config_root() / f"{provider.id}.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return provider


def remove_custom_provider(provider_id: str) -> bool:
    path = provider_config_root() / f"{provider_id}.json"
    if path.is_file():
        path.unlink()
        return True
    return False


def voice_metadata(provider: TTSProvider, voice_id: str) -> dict[str, str]:
    for voice in provider.voices:
        if voice["id"] == voice_id:
            return voice
    raise DubLocalError(f"Voice {voice_id!r} is not declared by {provider.label}.")


def provider_status_text() -> str:
    lines = ["```text", "[TTS providers] language → audited backend"]
    for provider in all_providers():
        installed = "ready · persistent local snapshot" if provider_is_installed(provider) else "not prepared"
        commercial = "commercial-use declared" if provider.manifest["license"].get("commercial_use") else "commercial-use NOT declared"
        source = provider.manifest["source"]
        if source["type"] == "huggingface":
            source_label = f"{source['repo_id']}@{source['revision']}"
        else:
            source_label = "local source"
        lines.append(
            f"[{provider.language}] {provider.label} · {installed} · {commercial} · {source_label}"
        )
    lines += [
        "[custom] JSON manifests are data-only; arbitrary Python/modules/commands are rejected",
        "[resilience] prepared providers run from DubLocal's persistent local copy, not from the remote fork",
        "```",
    ]
    return "\n".join(lines)
