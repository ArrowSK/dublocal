from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .app import LANGUAGE_CHOICES, TARGET_LANGUAGE_CHOICES


def _label(code: str | None) -> str:
    value = str(code or "").strip()
    for label, candidate in [*LANGUAGE_CHOICES, *TARGET_LANGUAGE_CHOICES]:
        if candidate == value:
            return label
    return value or "Unknown language"


def subtitles_ready_status(
    subtitle_path: str | None,
    rows: Sequence[Sequence[object]] | None,
    language: str | None,
    *,
    method: str,
) -> str:
    if not subtitle_path or not Path(subtitle_path).is_file():
        return "⚠ **Subtitles not ready** · see the warning or activity details."
    count = len(rows or [])
    return f"✓ **{method} · OK** · {count} timed segment{'s' if count != 1 else ''} · {_label(language)}"


def translation_ready_status(
    translated_path: str | None,
    rows: Sequence[Sequence[object]] | None,
    source_language: str | None,
    target_language: str | None,
) -> str:
    if not translated_path or not Path(translated_path).is_file():
        return "⚠ **Translation failed** · see the warning or activity details."
    count = len(rows or [])
    return (
        f"✓ **Translated · OK** · {count} segment{'s' if count != 1 else ''} · "
        f"{_label(source_language)} → {_label(target_language)}"
    )


def voice_ready_status(
    voice_path: str | None,
    rows: Sequence[Sequence[object]] | None,
    language: str | None,
    voice: str | None,
) -> str:
    if not voice_path or not Path(voice_path).is_file():
        return "⚠ **Voice generation failed** · see the warning or activity details."
    count = len(rows or [])
    voice_label = str(voice or "voice")
    return (
        f"✓ **Voice generated · OK** · {count} segment{'s' if count != 1 else ''} · "
        f"{_label(language)} · {voice_label}"
    )
