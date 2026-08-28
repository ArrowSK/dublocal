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


def _strip_echoed_segment_id(text: str, segment_id: int) -> str:
    """Remove an accidentally repeated protocol id from translated subtitle text.

    The contextual protocol already consumes the leading ``[ID] -`` marker. Some
    model responses occasionally echo the same id once more inside the payload,
    which previously leaked strings such as ``[49]`` into the written SRT. Only the
    exact current segment id at the beginning is removed; other bracketed content is
    preserved.
    """

    pattern = re.compile(rf"^\s*\[{int(segment_id)}\]\s*(?:[-:–—]\s*)?")
    cleaned = pattern.sub("", text or "", count=1).strip()
    return cleaned


def target_language_guidance(target_language: str) -> str:
    """Return concise target-language quality rules for the local LLM."""

    if target_language == "ru":
        return (
            "Write idiomatic contemporary Russian in Cyrillic. Do not calque English syntax; reconstruct natural Russian phrasing rather than "
            "mirroring English word order. Use correct case, noun gender, possessive/adjective agreement, number, tense and verbal aspect. "
            "For a continuous first-person speaker, determine grammatical gender only from reliable discourse context and then keep it consistent "
            "across past-tense verbs, short adjectives and participles. Do NOT infer the narrator's gender from a noun used only inside a comparison, "
            "metaphor or role description (for example, 'I feel like a woman/man'). If the speaker's gender is not actually established, actively "
            "rephrase into natural gender-neutral Russian instead of arbitrarily alternating masculine and feminine forms. Resolve pronouns and "
            "addressee/reference consistently across connected subtitle fragments. Translate idioms and phraseological expressions by their Russian "
            "meaning/register, not word-for-word. Preserve metaphors as metaphors, using a natural Russian equivalent image where a literal calque "
            "would sound absurd, without adding new imagery. Perform a final Russian grammar check for case government and agreement before output. "
            "Do not leave ordinary English words untranslated and do not create pseudo-Russian transliterations of English words. Render proper names "
            "naturally in Russian when appropriate. Preserve profanity at the source register rather than sanitising or intensifying it."
        )
    if target_language == "uk":
        return (
            "Write idiomatic contemporary Ukrainian in Cyrillic with natural grammar and word order. Resolve grammatical gender from context, "
            "translate idioms by meaning rather than literal wording, and preserve metaphors without inventing new imagery. Do not leave ordinary "
            "English words untranslated or create pseudo-Ukrainian transliterations. Preserve names and profanity naturally."
        )
    if target_language in _LATIN_TARGETS:
        return (
            "Write entirely in the requested target language using natural target-language grammar and idiom. Resolve grammatical gender/reference "
            "from context where the target language requires it. Translate idioms by meaning/register rather than literal word order, preserve source "
            "metaphors with a natural target-language equivalent, and avoid untranslated source-language fragments except unavoidable proper names."
        )
    return (
        "Write entirely in the requested target language using natural grammar and idiom. Resolve reference/gender from context without guessing, "
        "translate phraseological expressions by meaning, and preserve source metaphors without inventing new imagery."
    )


def _script_counts(text: str) -> tuple[int, int]:
    return len(_CYRILLIC_RE.findall(text)), len(_LATIN_RE.findall(text))


def validate_translation_text(
    text: str,
    *,
    target_language: str,
    segment_id: int,
) -> str:
    """Reject runtime leakage, unrelated scripts and substantial wrong-language leakage."""

    cleaned = _strip_echoed_segment_id(clean_generated_text(text), segment_id)
    if not cleaned:
        raise DubLocalError(f"Contextual translator returned no text for subtitle id {segment_id}.")

    marker = next((item for item in _RUNTIME_MARKERS if item.lower() in cleaned.lower()), None)
    if marker:
        raise DubLocalError(
            f"Contextual translator leaked local runtime text into subtitle id {segment_id} ({marker})."
        )

    if _CJK_OR_HANGUL_RE.search(cleaned):
        raise DubLocalError(
            f"Contextual translator produced unexpected non-target script (CJK/Hangul) in subtitle id {segment_id} "
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
