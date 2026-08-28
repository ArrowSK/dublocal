from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from platformdirs import user_cache_dir

from .timeline import Segment
from .translation import TranslatedSegment


_CACHE_SCHEMA = 1
_MAX_AGE_DAYS = 30
_MAX_ENTRIES = 256


@dataclass(frozen=True, slots=True)
class CachedTranslation:
    segments: list[TranslatedSegment]
    source_language: str
    target_language: str
    route: str


def translation_cache_root() -> Path:
    root = Path(user_cache_dir("DubLocal")) / "translations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def translation_cache_key(
    source_srt: str,
    *,
    requested_source_language: str,
    target_language: str,
    model_key: str,
    model_revision: str,
    model_sha256: str,
    review: bool,
    context_cap_tokens: int,
    chunk_segments: int,
    input_budget_tokens: int,
    prompt_version: str,
) -> str:
    payload = {
        "schema": _CACHE_SCHEMA,
        "source_srt": source_srt,
        "requested_source_language": requested_source_language,
        "target_language": target_language,
        "model_key": model_key,
        "model_revision": model_revision,
        "model_sha256": model_sha256,
        "review": bool(review),
        "context_cap_tokens": int(context_cap_tokens),
        "chunk_segments": int(chunk_segments),
        "input_budget_tokens": int(input_budget_tokens),
        "prompt_version": str(prompt_version),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _entry_path(key: str) -> Path:
    return translation_cache_root() / f"{key}.json"


def load_translation_cache(
    key: str,
    source_segments: Sequence[Segment],
    *,
    target_language: str,
) -> CachedTranslation | None:
    path = _entry_path(key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") != _CACHE_SCHEMA:
        return None
    if str(payload.get("target_language") or "") != target_language:
        return None

    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or len(raw_segments) != len(source_segments):
        return None

    translated: list[TranslatedSegment] = []
    for source, raw in zip(source_segments, raw_segments, strict=True):
        if not isinstance(raw, dict):
            return None
        try:
            index = int(raw["index"])
            start_ms = int(raw["start_ms"])
            end_ms = int(raw["end_ms"])
            text = str(raw["translated_text"])
        except (KeyError, TypeError, ValueError):
            return None
        if index != source.index or start_ms != source.start_ms or end_ms != source.end_ms:
            return None
        translated.append(
            TranslatedSegment(
                index=source.index,
                start_ms=source.start_ms,
                end_ms=source.end_ms,
                source_text=source.text,
                translated_text=text,
            )
        )

    try:
        path.touch()
    except OSError:
        pass
    return CachedTranslation(
        segments=translated,
        source_language=str(payload.get("source_language") or "auto"),
        target_language=target_language,
        route=str(payload.get("route") or "contextual translation"),
    )


def save_translation_cache(
    key: str,
    translated: Sequence[TranslatedSegment],
    *,
    source_language: str,
    target_language: str,
    route: str,
) -> None:
    root = translation_cache_root()
    path = root / f"{key}.json"
    payload = {
        "schema": _CACHE_SCHEMA,
        "source_language": source_language,
        "target_language": target_language,
        "route": route,
        "segments": [
            {
                "index": item.index,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "translated_text": item.translated_text,
            }
            for item in translated
        ],
    }
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return
    prune_translation_cache()


def prune_translation_cache(
    *,
    max_age_days: int = _MAX_AGE_DAYS,
    max_entries: int = _MAX_ENTRIES,
    now: float | None = None,
) -> None:
    root = translation_cache_root()
    current = time.time() if now is None else float(now)
    cutoff = current - max(0, int(max_age_days)) * 86400
    entries: list[tuple[Path, float]] = []
    for path in root.glob("*.json"):
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        if modified < cutoff:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        entries.append((path, modified))

    keep = max(0, int(max_entries))
    if len(entries) <= keep:
        return
    for path, _modified in sorted(entries, key=lambda item: item[1])[: len(entries) - keep]:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
