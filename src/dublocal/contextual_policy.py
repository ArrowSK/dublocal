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


# Bump whenever the translation/review instructions or context semantics change in a
# way that could alter output. The persistent translation cache includes this value.
CONTEXTUAL_PROMPT_VERSION = "2026-08-28.2"


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
        "recurring phrases, point of view and emotional register. Repeated refrains should use the same translation unless the source meaning changes. "
        "Do not invent cleaner or more plausible lyrics when ASR text is uncertain.\n"
        if _looks_like_music(all_segments)
        else ""
    )
    language_note = target_language_guidance(target_language)

    return (
        "/no_think\n"
        f"Translate the TARGET LINES from {source} to natural, idiomatic {target}.\n"
        "Accuracy is more important than creative paraphrasing. Preserve the actual meaning, names, tone, slang and profanity. DO NOT INVENT facts, words, imagery or speaker intent that are not supported by the source/context.\n"
        "Before translating, silently reconstruct complete thoughts across adjacent subtitle fragments. Then split the translation back across the same subtitle IDs without changing meaning or order.\n"
        "Use all supplied context to resolve pronouns, grammatical gender, who is speaking to whom, recurring terms, metaphors, idioms and references, but NEVER copy context lines into output.\n"
        "GENDER: infer speaker/addressee/referent gender only when the supplied programme or nearby context supports it. Keep that choice consistent across connected lines. If gender is genuinely ambiguous, prefer a natural target-language construction that does not invent an unsupported gender.\n"
        "IDIOMS / PHRASEOLOGISMS: translate the meaning and register with a natural target-language idiomatic equivalent when one exists; do not translate the words mechanically. Preserve jokes/puns when possible without inventing a different joke.\n"
        "METAPHORS: preserve the source metaphor, image and emotional force. Use a natural equivalent image in the target language when a literal calque sounds nonsensical; do not flatten a metaphor into plain prose unless no faithful natural rendering exists, and do not add new imagery.\n"
        "The source may come from automatic speech recognition. If wording is genuinely garbled, translate the visible source conservatively; do not guess or hallucinate the missing original wording.\n"
        + content_note
        + f"TARGET-LANGUAGE RULES: {language_note}\n"
        + "Standalone bracketed caption tags such as [MUSIC], [APPLAUSE] and [LAUGHTER] are protected by DubLocal. They are not TARGET LINES and must never be translated or emitted.\n"
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
        + "\n\nRECENT APPROVED TRANSLATIONS — preserve terminology/style/gender choices, do not output:\n"
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
    """Ask the loaded model for a conservative senior review.

    Normal translation prompts already contain the source TARGET LINES, so do not send
    them twice. Keep a source-lines fallback for direct/library callers that provide a
    different original prompt.
    """

    target = TRANSLATION_LANGUAGES[target_language]["label"]
    source_lines = [_segment_line(segment) for segment in target_segments]
    source_fallback = ""
    if not all(line in original_prompt for line in source_lines):
        source_fallback = "\n\nSOURCE TARGET LINES:\n" + "\n".join(source_lines)
    draft_lines = "\n".join(
        f"[{segment.index}] {text}"
        for segment, text in zip(target_segments, draft_texts, strict=True)
    )
    return (
        original_prompt.rstrip()
        + source_fallback
        + "\n\nSENIOR REVIEW PASS — improve the DRAFT TRANSLATIONS below before final output.\n"
        + f"Review against the source TARGET LINES and ALL programme/nearby context already supplied above. Output polished natural {target}.\n"
        + "Review connected subtitle fragments as continuous discourse, not independent sentences.\n"
        + "CHECK 1 — meaning: correct mistranslations and wrong lexical choices without inventing information.\n"
        + "CHECK 2 — gender/reference: verify grammatical gender, pronouns and speaker/addressee/referent relationships against context; keep them consistent, and avoid unsupported gender when context is ambiguous.\n"
        + "CHECK 3 — idioms/phraseology: replace literal calques with natural target-language idiomatic equivalents that preserve meaning and register.\n"
        + "CHECK 4 — metaphors: preserve the original image and emotional force; fix nonsensical literal calques without adding new imagery.\n"
        + "CHECK 5 — target grammar: fix case, gender, number, agreement, verbal aspect/tense, word order and punctuation.\n"
        + "CHECK 6 — continuity: keep recurring names, terminology, refrains and key phrases consistent across the chunk and prior approved translations.\n"
        + "CHECK 7 — register: preserve slang/profanity and humor at the source register; do not sanitize or intensify them.\n"
        + "Do NOT make the text more literary than the source. Do NOT guess missing ASR words. Do NOT change subtitle IDs.\n"
        + f"TARGET-LANGUAGE RULES: {target_language_guidance(target_language)}\n"
        + "Return EXACTLY one line per ID: [ID] - final translated text. No commentary.\n\n"
        + "DRAFT TRANSLATIONS TO REVIEW:\n"
        + draft_lines
        + "\n"
    )
