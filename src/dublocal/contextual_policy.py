from __future__ import annotations

from typing import Sequence

from .contextual_translation import (
    ContextPlan,
    _build_context_sections,
    _segment_line,
    context_budget_for_duration,
)
from .timeline import Segment
from .translation import TRANSLATION_LANGUAGES, TranslatedSegment
from .translation_quality import is_protected_caption_tag, target_language_guidance


def context_plan(segments: Sequence[Segment]) -> ContextPlan:
    """Plan fewer model calls for short media while keeping long-form context bounded."""

    duration_ms = max((segment.end_ms for segment in segments), default=0)
    minutes = duration_ms / 60_000.0
    if minutes <= 10:
        chunk_segments = 48
    elif minutes <= 30:
        chunk_segments = 36
    elif minutes <= 90:
        chunk_segments = 28
    else:
        chunk_segments = 24
    return ContextPlan(
        duration_ms=duration_ms,
        input_budget_tokens=context_budget_for_duration(duration_ms),
        chunk_segments=chunk_segments,
    )


def _looks_like_music(all_segments: Sequence[Segment]) -> bool:
    return any(
        is_protected_caption_tag(segment.text) and "MUSIC" in segment.text.upper()
        for segment in all_segments
    )


def build_translation_prompt(
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
    target_segments = [
        segment for segment in all_segments[start:end] if not is_protected_caption_tag(segment.text)
    ]
    global_lines, nearby_lines, previous_lines = _build_context_sections(
        all_segments, start, end, previous_translations, plan
    )
    target_lines = [_segment_line(segment) for segment in target_segments]
    content_note = (
        "The programme appears to contain song/music captions. Treat sung lines as lyrics: preserve imagery, repetition, "
        "recurring phrases, point of view and emotional register. Do not turn awkward ASR text into unrelated invented lyrics.\n"
        if _looks_like_music(all_segments)
        else ""
    )
    language_note = target_language_guidance(target_language)

    return (
        "/no_think\n"
        f"Translate the TARGET LINES from {source} to natural, idiomatic {target}.\n"
        "Accuracy is more important than creative paraphrasing. Preserve the actual meaning, names, tone, slang and profanity.\n"
        "Read adjacent subtitle fragments as continuous speech when grammar or meaning crosses subtitle boundaries.\n"
        "Use all supplied context to resolve pronouns, recurring terms, metaphors and references, but NEVER copy context lines into output.\n"
        "The source may come from automatic speech recognition. If wording is genuinely garbled, translate the visible source conservatively; "
        "do not hallucinate the missing original wording.\n"
        + content_note
        + f"TARGET-LANGUAGE RULES: {language_note}\n"
        + "Standalone bracketed caption tags such as [MUSIC], [APPLAUSE] and [LAUGHTER] are protected by DubLocal. "
        "They are not TARGET LINES and must never be translated or emitted.\n"
        f"Output must be entirely valid {target}. Do not switch into an unrelated writing system or leave ordinary source-language words untranslated.\n"
        "Keep each subtitle concise enough for screen reading without sacrificing essential meaning.\n"
        "Return EXACTLY one line per TARGET LINE in this form: [ID] - translated text\n"
        "Keep the same IDs and order. Do not output JSON, Markdown, headings, explanations, context lines or alternatives.\n\n"
        f"PROGRAMME DURATION: {plan.duration_ms / 60000.0:.1f} minutes\n"
        f"CONTEXT INPUT BUDGET: {plan.input_budget_tokens} tokens (grows with programme duration)\n\n"
        "GLOBAL PROGRAMME CONTEXT — reference only, do not output:\n"
        + ("\n".join(global_lines) if global_lines else "(none)")
        + "\n\nNEARBY SOURCE CONTEXT — reference only, do not output:\n"
        + ("\n".join(nearby_lines) if nearby_lines else "(none)")
        + "\n\nRECENT APPROVED TRANSLATIONS — preserve terminology/style, do not output:\n"
        + ("\n".join(previous_lines) if previous_lines else "(none)")
        + "\n\nTARGET LINES — translate these and only these:\n"
        + ("\n".join(target_lines) if target_lines else "(none)")
        + "\n"
    )


def build_review_prompt(
    original_prompt: str,
    target_segments: Sequence[Segment],
    draft_texts: Sequence[str],
    target_language: str,
) -> str:
    """Ask the same loaded model to act as a conservative senior translation reviewer."""

    target = TRANSLATION_LANGUAGES[target_language]["label"]
    source_lines = "\n".join(_segment_line(segment) for segment in target_segments)
    draft_lines = "\n".join(
        f"[{segment.index}] {text}"
        for segment, text in zip(target_segments, draft_texts, strict=True)
    )
    return (
        original_prompt.rstrip()
        + "\n\nSENIOR REVIEW PASS — improve the DRAFT TRANSLATIONS below before final output.\n"
        + f"Review against the English/source TARGET LINES and all context above. Output polished natural {target}.\n"
        + "Correct mistranslations, literal calques, wrong word choice, case/gender/number errors, broken idiom, untranslated ordinary words, "
        + "and inconsistent recurring phrases. Preserve slang/profanity at the same register.\n"
        + "Do NOT make the text more literary than the source. Do NOT guess missing ASR words. Do NOT change subtitle IDs.\n"
        + f"TARGET-LANGUAGE RULES: {target_language_guidance(target_language)}\n"
        + "Return EXACTLY one line per ID: [ID] - final translated text. No commentary.\n\n"
        + "SOURCE TARGET LINES:\n"
        + source_lines
        + "\n\nDRAFT TRANSLATIONS TO REVIEW:\n"
        + draft_lines
        + "\n"
    )
