from __future__ import annotations

import re
from typing import Sequence

from .contextual_translation import ContextPlan, _build_context_sections, _segment_line
from .media import DubLocalError
from .timeline import Segment
from .translation import TRANSLATION_LANGUAGES, TranslatedSegment


_BEGIN = "DUBLOCAL_TRANSLATION_BEGIN"
_END = "DUBLOCAL_TRANSLATION_END"
_ID_LINE_RE = re.compile(r"^\s*\[(\d+)\]\s*[-–—:]\s*(.*?)\s*$")


def build_line_translation_prompt(
    all_segments: Sequence[Segment],
    start: int,
    end: int,
    source_language: str,
    target_language: str,
    previous_translations: Sequence[TranslatedSegment],
    plan: ContextPlan,
) -> str:
    source = TRANSLATION_LANGUAGES[source_language]["label"]
    target = TRANSLATION_LANGUAGES[target_language]["label"]
    target_segments = all_segments[start:end]
    global_lines, nearby_lines, previous_lines = _build_context_sections(
        all_segments, start, end, previous_translations, plan
    )
    target_lines = [_segment_line(segment) for segment in target_segments]
    ids = ", ".join(str(segment.index) for segment in target_segments)

    music_hint = any(
        "music" in segment.text.lower() or "♪" in segment.text
        for segment in all_segments
    )
    material_note = (
        "This material appears to include song lyrics. Preserve lyrical continuity, repeated refrains, recurring metaphors and speaker voice. "
        "Do not freely rewrite odd source wording just to make it prettier; the source may contain ASR errors, and invention is worse than a cautious literal rendering.\n"
        if music_hint
        else ""
    )

    return (
        f"Translate the TARGET LINES from {source} to natural, accurate, idiomatic {target}.\n"
        "Use all supplied context to resolve pronouns, speaker intent, recurring names, slang, jokes and tone.\n"
        "Translate the meaning, not isolated dictionary words, but do not invent facts or repair uncertain source text without strong contextual evidence.\n"
        "Keep profanity and register when present; do not sanitize dialogue.\n"
        "For bracketed non-dialogue cues, preserve the brackets and use a conventional short subtitle cue in the target language.\n"
        "Prefer simple, natural target-language phrasing over awkward calques.\n"
        + material_note
        + f"Required subtitle IDs, exactly once and in this order: {ids}.\n"
        + f"Return only text between the two marker lines below. Inside them, return exactly one line per subtitle as [ID] - translated text.\n"
        + f"{_BEGIN}\n"
        + "[ID] - translated text\n"
        + f"{_END}\n\n"
        + f"PROGRAMME DURATION: {plan.duration_ms / 60000.0:.1f} minutes\n"
        + f"CONTEXT INPUT BUDGET: {plan.input_budget_tokens} tokens\n\n"
        + "GLOBAL PROGRAMME CONTEXT — reference only:\n"
        + ("\n".join(global_lines) if global_lines else "(none)")
        + "\n\nNEARBY SOURCE CONTEXT — reference only:\n"
        + ("\n".join(nearby_lines) if nearby_lines else "(none)")
        + "\n\nRECENT APPROVED TRANSLATIONS — preserve terminology/style:\n"
        + ("\n".join(previous_lines) if previous_lines else "(none)")
        + "\n\nTARGET LINES — translate these and only these:\n"
        + "\n".join(target_lines)
        + "\n\nNow output the final translation block only.\n"
    )


def extract_protocol_block(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise DubLocalError("Contextual translator returned no text.")

    begin = text.rfind(_BEGIN)
    if begin >= 0:
        begin += len(_BEGIN)
        end = text.find(_END, begin)
        if end >= 0:
            return text[begin:end].strip()

    # The HTTP server normally returns only model content. If the model omitted
    # markers, accept only a response made entirely of subtitle protocol lines.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and all(_ID_LINE_RE.match(line) for line in lines):
        return "\n".join(lines)

    raise DubLocalError("Contextual translator did not return a clean DubLocal subtitle block.")


def parse_line_translation(raw: str, target_segments: Sequence[Segment]) -> list[str]:
    block = extract_protocol_block(raw)
    expected = [segment.index for segment in target_segments]
    found: dict[int, str] = {}

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _ID_LINE_RE.match(stripped)
        if not match:
            raise DubLocalError("Contextual translator returned a malformed subtitle line.")
        index = int(match.group(1))
        text = match.group(2).strip()
        if not text:
            raise DubLocalError(f"Contextual translator returned empty text for subtitle id {index}.")
        if index in found:
            raise DubLocalError(f"Contextual translator returned subtitle id {index} more than once.")
        found[index] = text

    missing = [index for index in expected if index not in found]
    extra = [index for index in found if index not in expected]
    if missing or extra:
        raise DubLocalError(
            "Contextual translator did not preserve subtitle alignment "
            f"(missing={missing[:5]}, unexpected={extra[:5]})."
        )
    return [found[index] for index in expected]


def parse_partial_line_translation(raw: str, target_segments: Sequence[Segment]) -> dict[int, str]:
    expected = {segment.index for segment in target_segments}
    try:
        block = extract_protocol_block(raw)
    except DubLocalError:
        return {}

    found: dict[int, str] = {}
    conflicted: set[int] = set()
    for line in block.splitlines():
        match = _ID_LINE_RE.match(line.strip())
        if not match:
            continue
        index = int(match.group(1))
        text = match.group(2).strip()
        if index not in expected or not text:
            continue
        if index in found and found[index] != text:
            conflicted.add(index)
        else:
            found[index] = text
    for index in conflicted:
        found.pop(index, None)
    return found
