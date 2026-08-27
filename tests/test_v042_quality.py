from __future__ import annotations

import pytest

import dublocal.contextual_progress as contextual_progress
from dublocal.contextual_policy import build_review_prompt, context_plan
from dublocal.contextual_quality_model import QUALITY_CONTEXT_MODEL
from dublocal.media import DubLocalError
from dublocal.timeline import Segment
from dublocal.translation_quality import (
    is_protected_caption_tag,
    target_language_guidance,
    validate_translation_text,
)


def _segment(index: int, text: str) -> Segment:
    return Segment(index=index, start_ms=(index - 1) * 1000, end_ms=index * 1000, text=text)


def test_quality_model_is_official_pinned_and_permissive():
    assert QUALITY_CONTEXT_MODEL["repo_id"] == "Qwen/Qwen3-8B-GGUF"
    assert QUALITY_CONTEXT_MODEL["revision"] == "6a569868d07d3bd59e8b97fb001bf8c0b254bb20"
    assert QUALITY_CONTEXT_MODEL["filename"] == "Qwen3-8B-Q4_K_M.gguf"
    assert QUALITY_CONTEXT_MODEL["sha256"] == (
        "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
    )
    assert QUALITY_CONTEXT_MODEL["size"] == "5.03 GB"
    assert QUALITY_CONTEXT_MODEL["license"] == "Apache-2.0"


def test_short_song_is_planned_as_one_context_chunk():
    segments = [_segment(index, f"Lyric line {index}") for index in range(1, 35)]
    # Keep the final timestamp within ten minutes.
    segments[-1] = Segment(index=34, start_ms=330_000, end_ms=360_000, text="Last lyric")
    plan = context_plan(segments)
    assert plan.chunk_segments == 48
    assert len(segments) <= plan.chunk_segments


def test_caption_tags_are_structural_not_translation_text():
    assert is_protected_caption_tag("[MUSIC]")
    assert is_protected_caption_tag(" [APPLAUSE] ")
    assert is_protected_caption_tag("[MUSIC] [LAUGHTER]")
    assert not is_protected_caption_tag("Music starts now")


def test_russian_validation_rejects_cjk_contamination():
    with pytest.raises(DubLocalError, match="CJK/Hangul"):
        validate_translation_text(
            "Если я потеряю, где находится我的心, всё пропало.",
            target_language="ru",
            segment_id=12,
        )


def test_russian_validation_rejects_substantial_untranslated_latin_text():
    with pytest.raises(DubLocalError, match="Latin-script"):
        validate_translation_text(
            "Ты лучше попробуй этот fucking steak right now, пожалуйста.",
            target_language="ru",
            segment_id=30,
        )


def test_russian_validation_accepts_natural_cyrillic_with_name():
    assert validate_translation_text(
        "Меня зовут Ронни, я зависимый.",
        target_language="ru",
        segment_id=18,
    ) == "Меня зовут Ронни, я зависимый."


def test_russian_guidance_explicitly_forbids_calques_and_transliterated_nonsense():
    guidance = target_language_guidance("ru")
    assert "idiomatic contemporary Russian" in guidance
    assert "Do not calque English syntax" in guidance
    assert "pseudo-Russian" in guidance


def test_review_prompt_compares_source_and_draft_with_full_language_rules():
    targets = [
        _segment(3, "Well, I'm not a vampire, but I feel like one."),
        _segment(4, "Sometimes I sleep all day, cuz I hate the sun."),
    ]
    prompt = build_review_prompt(
        "ORIGINAL FULL CONTEXT PROMPT",
        targets,
        ["Я не вируп, но чувствую себя как вируп.", "Иногда я сплю весь день."],
        "ru",
    )
    assert "ORIGINAL FULL CONTEXT PROMPT" in prompt
    assert "SENIOR REVIEW PASS" in prompt
    assert "vampire" in prompt
    assert "Я не вируп" in prompt
    assert "Do not calque English syntax" in prompt


class _FakeRuntime:
    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)

    def generate(self, prompt: str, *, max_output_tokens: int) -> str:
        assert max_output_tokens > 0
        return self.outputs.pop(0)


def test_review_pass_can_improve_a_valid_draft():
    targets = [_segment(1, "Well, I'm not a vampire, but I feel like one.")]
    runtime = _FakeRuntime(["[1] - Я не вампир, но чувствую себя вампиром."])
    reviewed = contextual_progress._review_chunk(
        runtime,
        "full context",
        targets,
        ["Я не вампир, но чувствую себя как один."],
        "ru",
        max_output_tokens=512,
        chunk_number=1,
        total_chunks=1,
        progress_callback=None,
    )
    assert reviewed == ["Я не вампир, но чувствую себя вампиром."]


def test_review_failure_keeps_already_valid_draft():
    targets = [_segment(1, "Hello.")]
    runtime = _FakeRuntime(["review commentary without a subtitle id"])
    draft = ["Привет."]
    reviewed = contextual_progress._review_chunk(
        runtime,
        "full context",
        targets,
        draft,
        "ru",
        max_output_tokens=512,
        chunk_number=1,
        total_chunks=1,
        progress_callback=None,
    )
    assert reviewed == draft
