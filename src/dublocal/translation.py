from __future__ import annotations

import gc
import hashlib
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from platformdirs import user_cache_dir, user_data_dir

from .media import DubLocalError
from .timeline import Segment, parse_srt, segments_to_srt


TRANSLATION_LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"label": "English", "opus": "eng"},
    "hu": {"label": "Hungarian", "opus": "hun"},
    "ru": {"label": "Russian", "opus": "rus"},
    "de": {"label": "German", "opus": "deu"},
    "fr": {"label": "French", "opus": "fra"},
    "es": {"label": "Spanish", "opus": "spa"},
    "it": {"label": "Italian", "opus": "ita"},
    "pt": {"label": "Portuguese", "opus": "por"},
    "pl": {"label": "Polish", "opus": "pol"},
    "uk": {"label": "Ukrainian", "opus": "ukr"},
    "sr": {"label": "Serbian", "opus": "srp_Latn"},
    "hr": {"label": "Croatian", "opus": "hrv"},
}

# Exact immutable Hugging Face revisions containing safetensors equivalents of
# the Apache-2.0 OPUS Marian weights. The large weight itself is independently
# SHA-256 checked before the model is marked verified locally.
TRANSLATION_MODELS: dict[str, dict[str, str]] = {
    "many-to-en": {
        "label": "Many languages → English",
        "repo_id": "Helsinki-NLP/opus-mt-mul-en",
        "revision": "0f17725b72877e346bbcf9c28b842de32436a397",
        "weight_sha256": "8b8ff7a54cd65dd0015c620755dd62f956796035d2cafd43446e960e13c79c28",
        "weight_size": "310 MiB",
        "license": "Apache-2.0",
    },
    "en-to-many": {
        "label": "English → many languages",
        "repo_id": "Helsinki-NLP/opus-mt-en-mul",
        "revision": "d41ab23bbe31592b09f084b7063f1460a84600aa",
        "weight_sha256": "dd4c874ecad8853d94415c21937c7e35ea09cc22f178b63821294ed010121436",
        "weight_size": "310 MiB",
        "license": "Apache-2.0",
    },
}

_MODEL_FILES = [
    "config.json",
    "generation_config.json",
    "metadata.json",
    "model.safetensors",
    "source.spm",
    "target.spm",
    "tokenizer_config.json",
    "vocab.json",
]
_VERIFIED_MARKER = ".dublocal-verified.json"

_LANGUAGE_ALIASES = {
    "eng": "en",
    "en": "en",
    "hun": "hu",
    "hu": "hu",
    "rus": "ru",
    "ru": "ru",
    "deu": "de",
    "ger": "de",
    "de": "de",
    "fra": "fr",
    "fre": "fr",
    "fr": "fr",
    "spa": "es",
    "es": "es",
    "ita": "it",
    "it": "it",
    "por": "pt",
    "pt": "pt",
    "pol": "pl",
    "pl": "pl",
    "ukr": "uk",
    "uk": "uk",
    "srp": "sr",
    "sr": "sr",
    "hrv": "hr",
    "hr": "hr",
}


class TranslationEngineMissingError(DubLocalError):
    """Raised when the optional translation Python stack is not installed."""


class TranslationModelMissingError(DubLocalError):
    """Raised when a required local translation model is not installed."""


@dataclass(frozen=True, slots=True)
class TranslatedSegment:
    index: int
    start_ms: int
    end_ms: int
    source_text: str
    translated_text: str


@dataclass(frozen=True, slots=True)
class TranslationResult:
    srt_path: Path
    segments: list[TranslatedSegment]
    source_language: str
    target_language: str
    route: str


def translation_models_dir() -> Path:
    root = Path(user_data_dir("DubLocal")) / "models" / "translation"
    root.mkdir(parents=True, exist_ok=True)
    return root


def translation_model_path(model_id: str) -> Path:
    if model_id not in TRANSLATION_MODELS:
        raise DubLocalError(f"Unknown translation model: {model_id}")
    return translation_models_dir() / model_id


def _new_job_dir(prefix: str) -> Path:
    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=root))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise_language_code(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    if not raw or raw in {"auto", "und", "unknown"}:
        return "auto"

    candidates = [raw, raw.split("-", 1)[0]]
    for candidate in candidates:
        if candidate in _LANGUAGE_ALIASES:
            return _LANGUAGE_ALIASES[candidate]
    return "auto"


def translation_engine_ready() -> bool:
    return all(
        importlib.util.find_spec(module) is not None
        for module in ("torch", "transformers", "sentencepiece", "safetensors")
    )


def translation_engine_status() -> str:
    if translation_engine_ready():
        return "ready · PyTorch + Transformers + SentencePiece + safetensors"
    return "not installed · optional local translation engine"


def _repository_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if not (root / "pyproject.toml").is_file():
        raise DubLocalError("DubLocal could not locate its installation folder.")
    return root


def install_translation_engine() -> None:
    if translation_engine_ready():
        return

    root = _repository_root()
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", f"{root}[translation]"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DubLocalError(f"Could not install the local translation engine: {message}") from exc

    importlib.invalidate_caches()
    if not translation_engine_ready():
        raise DubLocalError(
            "The translation packages were installed, but this running DubLocal process cannot load them yet. "
            "Restart DubLocal once, then click Prepare translation again."
        )


def _verification_marker(model_id: str) -> Path:
    return translation_model_path(model_id) / _VERIFIED_MARKER


def _model_valid(model_id: str) -> bool:
    metadata = TRANSLATION_MODELS[model_id]
    directory = translation_model_path(model_id)
    if not all((directory / name).is_file() for name in _MODEL_FILES):
        return False

    marker = _verification_marker(model_id)
    if not marker.is_file():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    return (
        payload.get("repo_id") == metadata["repo_id"]
        and payload.get("revision") == metadata["revision"]
        and payload.get("weight_sha256") == metadata["weight_sha256"]
    )


def installed_translation_models() -> list[str]:
    return [model_id for model_id in TRANSLATION_MODELS if _model_valid(model_id)]


def install_translation_model(model_id: str) -> Path:
    metadata = TRANSLATION_MODELS.get(model_id)
    if not metadata:
        raise DubLocalError(f"Unknown translation model: {model_id}")
    if not translation_engine_ready():
        raise TranslationEngineMissingError(
            "The local translation engine is not installed. Click Prepare translation first."
        )

    destination = translation_model_path(model_id)
    if _model_valid(model_id):
        return destination

    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=metadata["repo_id"],
            revision=metadata["revision"],
            local_dir=str(destination),
            allow_patterns=_MODEL_FILES,
        )
    except Exception as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise DubLocalError(f"Translation model download failed: {exc}") from exc

    weight = destination / "model.safetensors"
    if not weight.is_file() or _sha256(weight) != metadata["weight_sha256"]:
        shutil.rmtree(destination, ignore_errors=True)
        raise DubLocalError(
            "Downloaded translation weights failed checksum verification. "
            "The model was deleted rather than used."
        )

    missing = [name for name in _MODEL_FILES if not (destination / name).is_file()]
    if missing:
        shutil.rmtree(destination, ignore_errors=True)
        raise DubLocalError(
            "The translation model download is incomplete: " + ", ".join(missing)
        )

    _verification_marker(model_id).write_text(
        json.dumps(
            {
                "repo_id": metadata["repo_id"],
                "revision": metadata["revision"],
                "weight_sha256": metadata["weight_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def remove_translation_models() -> int:
    removed = 0
    for model_id in TRANSLATION_MODELS:
        path = translation_model_path(model_id)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def required_model_ids(source_language: str, target_language: str) -> list[str]:
    source = normalise_language_code(source_language)
    target = normalise_language_code(target_language)
    if source == "auto":
        raise DubLocalError("Choose the subtitle source language before preparing translation.")
    if target == "auto":
        raise DubLocalError("Choose a translation target language.")
    if source not in TRANSLATION_LANGUAGES or target not in TRANSLATION_LANGUAGES:
        raise DubLocalError("That language is not enabled in DubLocal's M3 translation allowlist.")
    if source == target:
        return []
    if source == "en":
        return ["en-to-many"]
    if target == "en":
        return ["many-to-en"]
    return ["many-to-en", "en-to-many"]


def translation_route(source_language: str, target_language: str) -> str:
    source = normalise_language_code(source_language)
    target = normalise_language_code(target_language)
    if source == "auto" or target == "auto":
        return "choose source and target languages"
    if source == target:
        return "source and target are the same"
    if source == "en":
        return f"English → {TRANSLATION_LANGUAGES[target]['label']}"
    if target == "en":
        return f"{TRANSLATION_LANGUAGES[source]['label']} → English"
    return (
        f"{TRANSLATION_LANGUAGES[source]['label']} → English → "
        f"{TRANSLATION_LANGUAGES[target]['label']}"
    )


def translation_manager_status(
    source_language: str = "auto",
    target_language: str = "en",
) -> str:
    installed = set(installed_translation_models())
    lines = [f"[engine] {translation_engine_status()}"]
    for model_id, metadata in TRANSLATION_MODELS.items():
        state = "installed" if model_id in installed else "not installed"
        lines.append(
            f"[model] {metadata['label']} · {state} · {metadata['weight_size']} · {metadata['license']}"
        )
    lines.append(f"[route] {translation_route(source_language, target_language)}")
    return "```text\n" + "\n".join(lines) + "\n```"


def prepare_translation(source_language: str, target_language: str) -> list[str]:
    model_ids = required_model_ids(source_language, target_language)
    if not model_ids:
        raise DubLocalError("Source and target languages are the same; no translation is needed.")

    install_translation_engine()
    for model_id in model_ids:
        install_translation_model(model_id)
    return model_ids


def _ensure_translation_ready(source_language: str, target_language: str) -> list[str]:
    if not translation_engine_ready():
        raise TranslationEngineMissingError(
            "Local translation is not prepared yet. Click Prepare translation first."
        )
    model_ids = required_model_ids(source_language, target_language)
    if not model_ids:
        raise DubLocalError("Source and target languages are the same; no translation is needed.")
    missing = [model_id for model_id in model_ids if not _model_valid(model_id)]
    if missing:
        names = ", ".join(TRANSLATION_MODELS[item]["label"] for item in missing)
        raise TranslationModelMissingError(
            f"Required local translation model(s) are missing: {names}. Click Prepare translation."
        )
    return model_ids


def _device_name(torch_module) -> str:
    try:
        if torch_module.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _cleanup_model(torch_module, model) -> None:
    del model
    gc.collect()
    try:
        if torch_module.backends.mps.is_available():
            torch_module.mps.empty_cache()
    except Exception:
        pass


def _translate_with_model(
    model_id: str,
    texts: list[str],
    *,
    target_language: str | None = None,
    batch_size: int = 8,
) -> list[str]:
    if not texts:
        return []

    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    directory = translation_model_path(model_id)
    tokenizer = AutoTokenizer.from_pretrained(
        str(directory),
        local_files_only=True,
        trust_remote_code=False,
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        str(directory),
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
    )
    model.eval()

    device = _device_name(torch)
    if device != "cpu":
        model.to(device)

    prepared = list(texts)
    if model_id == "en-to-many":
        target = normalise_language_code(target_language)
        if target not in TRANSLATION_LANGUAGES or target == "en":
            _cleanup_model(torch, model)
            raise DubLocalError("Invalid English-to-multilingual target language.")
        tag = TRANSLATION_LANGUAGES[target]["opus"]
        prepared = [f">>{tag}<< {text}" for text in texts]

    def run_on_device(active_device: str) -> list[str]:
        outputs: list[str] = []
        for start in range(0, len(prepared), batch_size):
            batch_text = prepared[start : start + batch_size]
            encoded = tokenizer(
                batch_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            encoded = {key: value.to(active_device) for key, value in encoded.items()}
            with torch.inference_mode():
                generated = model.generate(**encoded, max_length=512)
            outputs.extend(
                tokenizer.batch_decode(
                    generated,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )
            )
        return [text.strip() for text in outputs]

    try:
        try:
            translated = run_on_device(device)
        except RuntimeError:
            if device == "cpu":
                raise
            model.to("cpu")
            translated = run_on_device("cpu")
    finally:
        _cleanup_model(torch, model)

    return translated


def translate_segments(
    segments: Iterable[Segment],
    source_language: str,
    target_language: str,
) -> list[TranslatedSegment]:
    source = normalise_language_code(source_language)
    target = normalise_language_code(target_language)
    _ensure_translation_ready(source, target)

    original = list(segments)
    texts = [segment.text.replace("\n", " ").strip() for segment in original]

    if source == "en":
        translated = _translate_with_model("en-to-many", texts, target_language=target)
    elif target == "en":
        translated = _translate_with_model("many-to-en", texts)
    else:
        english = _translate_with_model("many-to-en", texts)
        translated = _translate_with_model("en-to-many", english, target_language=target)

    if len(translated) != len(original):
        raise DubLocalError("Translation returned a different number of subtitle segments.")

    return [
        TranslatedSegment(
            index=segment.index,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            source_text=segment.text,
            translated_text=text,
        )
        for segment, text in zip(original, translated, strict=True)
    ]


def translate_srt(
    subtitle_path: str | Path,
    source_language: str,
    target_language: str,
) -> TranslationResult:
    path = Path(subtitle_path).expanduser().resolve()
    if not path.is_file():
        raise DubLocalError("The subtitle file is no longer available. Extract or transcribe it again.")
    if path.suffix.lower() != ".srt":
        raise DubLocalError(
            "M3 translates normalized SRT timelines. Re-extract the caption with the current DubLocal build first."
        )

    try:
        source_segments = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not read the subtitle timeline: {exc}") from exc
    if not source_segments:
        raise DubLocalError("The subtitle file contains no timed text to translate.")

    source = normalise_language_code(source_language)
    target = normalise_language_code(target_language)
    translated = translate_segments(source_segments, source, target)

    output_dir = _new_job_dir("translation")
    output = output_dir / f"captions.{target}.srt"
    translated_as_segments = [
        Segment(
            index=item.index,
            start_ms=item.start_ms,
            end_ms=item.end_ms,
            text=item.translated_text,
        )
        for item in translated
    ]
    output.write_text(segments_to_srt(translated_as_segments), encoding="utf-8")

    return TranslationResult(
        srt_path=output,
        segments=translated,
        source_language=source,
        target_language=target,
        route=translation_route(source, target),
    )


def translated_segments_to_rows(segments: Iterable[TranslatedSegment]) -> list[list[str]]:
    from .timeline import format_timestamp

    return [
        [
            format_timestamp(segment.start_ms),
            format_timestamp(segment.end_ms),
            segment.source_text,
            segment.translated_text,
        ]
        for segment in segments
    ]
