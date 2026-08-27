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
from .translation_quality import is_protected_caption_tag


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
    looks_like_music = any(is_protected_caption_tag(segment.text) and "MUSIC" in segment.text.upper() for segment in all_segments)
    content_note = (
        "The programme appears to contain song/music captions. Treat spoken/sung lines as lyrics: preserve imagery, "
        "repetition, recurring phrases and meaning; do not replace difficult wording with unrelated guesses.\n"
        if looks_like_music
        else ""
    )

    return (
        "/no_think\n"
        f"Translate the TARGET LINES from {source} to natural, idiomatic {target}.\n"
        "Accuracy is more important than creative paraphrasing. Preserve the actual meaning, names, tone, slang and profanity.\n"
        "Use all supplied context to resolve pronouns, recurring terms and sentence fragments across subtitle boundaries.\n"
        "The source may come from automatic speech recognition. If wording looks garbled or uncertain, translate conservatively; "
        "do not invent a different sentence to make it sound smoother.\n"
        + content_note
        + "Standalone bracketed caption tags such as [MUSIC], [APPLAUSE] and [LAUGHTER] are protected by DubLocal. "
        "They are not TARGET LINES and must never be translated or emitted.\n"
        f"Output must be in {target}. Do not switch into Chinese, Japanese, Korean or another unrelated writing system.\n"
        "Keep each subtitle concise enough for screen reading.\n"
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
