from __future__ import annotations

from dublocal.contextual_translation import (
    QWEN_CONTEXT_MODEL,
    _parse_chunk_output,
    build_translation_prompt,
    context_budget_for_duration,
    context_plan,
)
from dublocal.timeline import Segment
from dublocal.translation import TranslatedSegment


def _segments(count: int, *, step_ms: int = 10_000) -> list[Segment]:
    return [
        Segment(
            index=index + 1,
            start_ms=index * step_ms,
            end_ms=(index + 1) * step_ms,
            text=f"Line {index + 1} about recurring character Alex and the situation.",
        )
        for index in range(count)
    ]


def test_context_budget_grows_with_video_duration_and_is_bounded():
    short = context_budget_for_duration(5 * 60_000)
    feature = context_budget_for_duration(90 * 60_000)
    very_long = context_budget_for_duration(10 * 60 * 60_000)

    assert 4096 <= short < feature < very_long
    assert very_long == 24576


def test_longer_programme_uses_larger_translation_plan():
    short = context_plan(_segments(30, step_ms=10_000))
    long = context_plan(_segments(900, step_ms=10_000))

    assert long.input_budget_tokens > short.input_budget_tokens
    assert long.chunk_segments >= short.chunk_segments


def test_prompt_contains_global_nearby_and_translation_memory_context():
    segments = _segments(40)
    previous = [
        TranslatedSegment(
            index=1,
            start_ms=0,
            end_ms=10_000,
            source_text="Alex is here.",
            translated_text="Алекс здесь.",
        )
    ]
    plan = context_plan(segments)
    prompt = build_translation_prompt(
        segments,
        10,
        22,
        "en",
        "ru",
        previous,
        plan,
    )

    assert "GLOBAL PROGRAMME CONTEXT" in prompt
    assert "NEARBY SOURCE CONTEXT" in prompt
    assert "RECENT APPROVED TRANSLATIONS" in prompt
    assert "Алекс здесь." in prompt
    assert "TARGET LINES" in prompt
    assert "[11]" in prompt
    assert "[22]" in prompt
    assert "[10]" in prompt  # nearby context, not a target id
    assert str(plan.input_budget_tokens) in prompt
    assert "Do not translate sentence-by-sentence in isolation" in prompt


def test_chunk_parser_preserves_requested_segment_order():
    targets = _segments(3)
    raw = 'runtime chatter\n[{"id": 1, "text": "Один"}, {"id": 2, "text": "Два"}, {"id": 3, "text": "Три"}]\n'
    assert _parse_chunk_output(raw, targets) == ["Один", "Два", "Три"]


def test_context_model_is_permissive_and_checksum_pinned():
    assert QWEN_CONTEXT_MODEL["repo_id"] == "Qwen/Qwen3-4B-GGUF"
    assert QWEN_CONTEXT_MODEL["license"] == "Apache-2.0"
    assert len(str(QWEN_CONTEXT_MODEL["revision"])) == 40
    assert len(str(QWEN_CONTEXT_MODEL["sha256"])) == 64
