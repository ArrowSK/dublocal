from __future__ import annotations

from dublocal.contextual_policy import (
    CONTEXTUAL_PROMPT_VERSION,
    build_review_prompt,
    build_translation_prompt,
    context_plan,
)
from dublocal.timeline import Segment


def _segments(count: int, step_ms: int = 10_000) -> list[Segment]:
    return [
        Segment(
            index=index + 1,
            start_ms=index * step_ms,
            end_ms=(index + 1) * step_ms,
            text="[MUSIC]" if index == 0 else f"Line {index + 1} of the song.",
        )
        for index in range(count)
    ]


def test_short_song_uses_one_large_chunk_instead_of_many_model_reloads():
    segments = _segments(36, step_ms=10_000)  # six minutes
    plan = context_plan(segments)
    assert plan.chunk_segments == 48
    assert len(segments) <= plan.chunk_segments


def test_longer_media_gets_more_context_but_bounded_chunk_sizes():
    short = context_plan(_segments(30, step_ms=10_000))
    feature = context_plan(_segments(540, step_ms=10_000))
    assert feature.input_budget_tokens > short.input_budget_tokens
    assert short.chunk_segments == 48
    assert feature.chunk_segments == 28


def test_prompt_protects_tags_and_uses_faithful_line_protocol():
    segments = _segments(8)
    plan = context_plan(segments)
    prompt = build_translation_prompt(segments, 0, len(segments), "en", "ru", [], plan)
    target_section = prompt.split("TARGET LINES — translate these and only these:", 1)[1]
    assert "[MUSIC]" not in target_section
    assert "must never be translated" in prompt
    assert "do not invent" in prompt.lower()
    assert "[ID] - translated text" in prompt
    assert "Do not output JSON" in prompt
    assert "lyrics" in prompt


def test_review_reuses_source_context_without_duplicating_target_lines():
    segments = [
        Segment(1, 0, 1000, "Hello there."),
        Segment(2, 1000, 2000, "How are you?"),
    ]
    plan = context_plan(segments)
    original = build_translation_prompt(segments, 0, 2, "en", "ru", [], plan)
    review = build_review_prompt(
        original,
        segments,
        ["Привет.", "Как дела?"],
        "ru",
    )
    assert review.count("[1] Hello there.") == original.count("[1] Hello there.")
    assert "DRAFT TRANSLATIONS TO REVIEW" in review
    assert "[1] Привет." in review
    assert "CHECK 7" in review
    assert CONTEXTUAL_PROMPT_VERSION
