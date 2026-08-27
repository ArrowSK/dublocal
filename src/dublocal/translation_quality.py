from __future__ import annotations

import re

from .media import DubLocalError


_STANDALONE_TAG_RE = re.compile(r"^\s*(?:\[[^\]\r\n]{1,120}\]\s*)+$")
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CJK_OR_HANGUL_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]"
)
_RUNTIME_MARKERS = (
    "Loading model",
    "available commands",
    "using custom system prompt",
    "build      :",
    "model      :",
    "ftype      :",
    "modalities :",
    "/no_think",
    "TARGET LINES",
    "FINAL SINGLE-SUBTITLE RECOVERY TASK",
    "Exiting...",
    ".gguf",
)


def is_protected_caption_tag(text: str) -> bool:
    """Return True for standalone caption cues such as [MUSIC] or [APPLAUSE]."""

    return bool(_STANDALONE_TAG_RE.fullmatch(text or ""))


def clean_generated_text(text: str) -> str:
    """Remove terminal escapes/control characters without altering normal Unicode text."""

    cleaned = _ANSI_RE.sub("", text or "").replace("\b", "")
    cleaned = "".join(char for char in cleaned if char in "\n\t" or ord(char) >= 32)
    return cleaned.strip()


def validate_translation_text(
    text: str,
    *,
    target_language: str,
    segment_id: int,
) -> str:
    """Reject obvious runtime leakage or wrong-script contamination before writing subtitles."""

    cleaned = clean_generated_text(text)
    if not cleaned:
        raise DubLocalError(f"Contextual translator returned no text for subtitle id {segment_id}.")

    marker = next((item for item in _RUNTIME_MARKERS if item.lower() in cleaned.lower()), None)
    if marker:
        raise DubLocalError(
            f"Contextual translator leaked local runtime text into subtitle id {segment_id} ({marker})."
        )

    # DubLocal's current translation targets are European-language sets. CJK/Hangul
    # characters therefore indicate model contamination rather than legitimate target text.
    if _CJK_OR_HANGUL_RE.search(cleaned):
        raise DubLocalError(
            f"Contextual translator produced unexpected non-target script in subtitle id {segment_id} "
            f"while translating to {target_language}."
        )

    return cleaned
