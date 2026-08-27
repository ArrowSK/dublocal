from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from .media import DubLocalError


_UNSAFE_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]+")
_SPACE_RE = re.compile(r"\s+")


def safe_media_stem(info: dict[str, Any] | None) -> str:
    """Return a human-friendly filesystem-safe stem derived from the loaded media."""

    payload = info or {}
    raw = str(payload.get("title") or "media").strip()
    if payload.get("kind") == "local":
        path = Path(str(payload.get("path") or raw))
        raw = path.stem or Path(raw).stem or raw
    else:
        raw = Path(raw).stem if Path(raw).suffix else raw

    value = _UNSAFE_RE.sub(" ", raw)
    value = _SPACE_RE.sub(" ", value).strip(" .-_\t\n")
    if not value:
        value = "media"
    # Leave room for language/dub suffixes and container extensions.
    return value[:140].rstrip(" .-_\t\n") or "media"


def safe_language_suffix(language: str | None) -> str:
    raw = (language or "und").strip().replace("_", "-")
    cleaned = re.sub(r"[^A-Za-z0-9-]+", "", raw)
    return cleaned or "und"


def friendly_subtitle_path(
    source_path: str | Path,
    info: dict[str, Any] | None,
    language: str | None,
) -> Path:
    """Copy an internal SRT to a readable `<media>.<language>.srt` filename."""

    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("The generated subtitle file is no longer available.")
    destination = source.parent / f"{safe_media_stem(info)}.{safe_language_suffix(language)}.srt"
    if source == destination:
        return source
    shutil.copy2(source, destination)
    return destination


def dubbed_media_path(
    directory: str | Path,
    info: dict[str, Any] | None,
    language: str | None,
    extension: str,
) -> Path:
    ext = extension.lower().lstrip(".")
    if ext not in {"mkv", "mp4", "m4a", "mka"}:
        raise DubLocalError(f"Unsupported DubLocal output extension: {extension}")
    return Path(directory) / (
        f"{safe_media_stem(info)}.dub.{safe_language_suffix(language)}.{ext}"
    )
