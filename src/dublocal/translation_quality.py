from __future__ import annotations

import re

from .media import DubLocalError


_STANDALONE_TAG_RE = re.compile(r"^\s*(?:\[[^\]\r\n]{1,120}\]\s*)+$")
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CJK_OR_HANGUL_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]"
)
_CYRILLIC_RE = re.compile(r"[\u0400-\u052f]")
_LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]")
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
_CYRILLIC_TARGETS = {"ru", "uk"}
_LATIN_TARGETS = {"en", "hu", "de", "fr", "es", "it", "pt", "pl", "sr", "hr"}


def is_protected_caption_tag(text: str) -> bool:
    """Return True for standalone caption cues such as [MUSIC] or [APPLAUSE]."""

    return bool(_STANDALONE_TAG_RE.fullmatch(text or ""))


def clean_generated_text(text: str) -> str:
    """Remove terminal escapes/control characters without altering normal Unicode text."""

    cleaned = _ANSI_RE.sub("", text or "").replace("\b", "")
    cleaned = "".join(char for char in cleaned if char in "\n\t" or ord(char) >= 32)
    return cleaned.strip()


def target_language_guidance(target_language: str) -> str:
    """Return concise target-language quality rules for the local LLM."""

    if target_language == "ru":
        return (
            "Write idiomatic contemporary Russian in Cyrillic. Use correct case, gender, number and verbal aspect. "
            "Do not calque English syntax. Do not leave ordinary English words untranslated and do not create pseudo-Russian "
            "transliterations of English words. Render proper names naturally in Russian when appropriate. Preserve profanity "
            "at the source register rather than sanitising or intensifying it."
        )
    if target_language == "uk":
        return (
            "Write idiomatic contemporary Ukrainian in Cyrillic with natural grammar and word order. Do not leave ordinary "
            "English words untranslated or create pseudo-Ukrainian transliterations. Preserve names and profanity naturally."
        )
    if target_language in _LATIN_TARGETS:
        return (
            "Write entirely in the requested target language using natural target-language grammar and idiom. Avoid literal "
            "English calques and untranslated source-language fragments except unavoidable proper names."
        )
    return "Write entirely in the requested target language using natural grammar and idiom."


def _script_counts(text: str) -> tuple[int, int]:
    return len(_CYRILLIC_RE.findall(text)), len(_LATIN_RE.findall(text))


def validate_translation_text(
    text: str,
    *,
    target_language: str,
    segment_id: int,
) -> str:
    """Reject runtime leakage, unrelated scripts and substantial wrong-language leakage."""

    cleaned = clean_generated_text(text)
    if not cleaned:
        raise DubLocalError(f"Contextual translator returned no text for subtitle id {segment_id}.")

    marker = next((item for item in _RUNTIME_MARKERS if item.lower() in cleaned.lower()), None)
    if marker:
        raise DubLocalError(
            f"Contextual translator leaked local runtime text into subtitle id {segment_id} ({marker})."
        )

    if _CJK_OR_HANGUL_RE.search(cleaned):
        raise DubLocalError(
            f"Contextual translator produced unexpected CJK/Hangul text in subtitle id {segment_id} "
            f"while translating to {target_language}."
        )

    cyrillic, latin = _script_counts(cleaned)
    alphabetic = cyrillic + latin
    if target_language in _CYRILLIC_TARGETS and alphabetic >= 8:
        # A proper name can remain Latin, but a Russian/Ukrainian subtitle must not contain
        # substantial untranslated English such as 'steak', 'oh real' or whole clauses.
        if latin >= 5 and latin / alphabetic > 0.18:
            raise DubLocalError(
                f"Contextual translator left too much Latin-script text in subtitle id {segment_id} "
                f"while translating to {target_language}."
            )
    elif target_language in _LATIN_TARGETS and alphabetic >= 8:
        if cyrillic >= 5 and cyrillic / alphabetic > 0.18:
            raise DubLocalError(
                f"Contextual translator left too much Cyrillic text in subtitle id {segment_id} "
                f"while translating to {target_language}."
            )

    return cleaned
