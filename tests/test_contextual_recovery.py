from __future__ import annotations

import json

from dublocal.contextual_recovery import (
    build_format_repair_prompt,
    build_missing_recovery_prompt,
    build_single_line_recovery_prompt,
    clean_single_line_output,
    recover_chunk_output,
    recover_partial_output,
)
from dublocal.timeline import Segment


def _targets() -> list[Segment]:
    return [
        Segment(index=1, start_ms=0, end_ms=1000, text="Hello."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="How are you?"),
    ]


def test_recovers_wrapped_translation_array():
    raw = json.dumps(
        {
            "translations": [
                {"id": 1, "text": "Привет."},
                {"id": 2, "text": "Как дела?"},
            ]
        },
        ensure_ascii=False,
    )
    assert recover_chunk_output(raw, _targets()) == ["Привет.", "Как дела?"]


def test_recovers_markdown_code_fence():
    raw = "Result:\n```json\n[{\"id\":1,\"text\":\"Привет.\"},{\"id\":2,\"text\":\"Как дела?\"}]\n```"
    assert recover_chunk_output(raw, _targets()) == ["Привет.", "Как дела?"]


def test_recovers_id_prefixed_lines_without_weakening_alignment():
    raw = "[1] - Привет.\n[2] - Как дела?"
    assert recover_chunk_output(raw, _targets()) == ["Привет.", "Как дела?"]


def test_recovers_common_qwen_numbering_variants_with_explicit_ids():
    raw = "1. Hello.\nID 2: How are you?"
    assert recover_chunk_output(raw, _targets()) == ["Hello.", "How are you?"]


def test_recovers_exact_ordered_bare_lines_only_when_count_matches():
    raw = "Hello.\nHow are you?"
    assert recover_chunk_output(raw, _targets()) == ["Hello.", "How are you?"]
    assert recover_partial_output("Only one line.", _targets()) == {}


def test_recovers_exact_json_string_list_by_position():
    raw = json.dumps(["Hello.", "How are you?"])
    assert recover_chunk_output(raw, _targets()) == ["Hello.", "How are you?"]


def test_repair_prompt_names_target_language_and_ids():
    prompt = build_format_repair_prompt("bad output", _targets(), "Russian")
    assert "natural Russian" in prompt
    assert "1, 2" in prompt
    assert "bad output" in prompt
    assert "[ID] - translated text" in prompt
    assert "Do not output JSON" in prompt


def test_missing_recovery_focuses_on_missing_source_lines():
    targets = [
        Segment(index=1, start_ms=0, end_ms=1000, text="Already translated."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="Translate this."),
        Segment(index=3, start_ms=2000, end_ms=3000, text="And this."),
    ]
    prompt = build_missing_recovery_prompt(
        "programme context",
        targets,
        targets[1:],
        {1: "Done."},
        "English",
        "bad previous output",
    )
    source_section = prompt.split("MISSING SOURCE LINES", 1)[1].split("RECENT CHUNK CONTEXT", 1)[0]
    assert "[2] Translate this." in source_section
    assert "[3] And this." in source_section
    assert "[1] Already translated." not in source_section
    assert "Missing IDs (2): 2, 3" in prompt


def test_single_line_recovery_does_not_resend_huge_programme_prompt():
    huge_context = "EARLY CONTEXT\n" + ("old programme detail " * 3000) + "\nTARGET LINES\n[69] Ez egy teszt."
    prompt = build_single_line_recovery_prompt(
        huge_context,
        Segment(index=69, start_ms=0, end_ms=1000, text="Ez egy teszt."),
        "English",
        "[68] - Previous line",
    )
    assert len(prompt) < 9000
    assert "[earlier programme context omitted for fast recovery]" in prompt
    assert "[69] Ez egy teszt." in prompt
    assert "Translate ONLY subtitle [69]" in prompt


def test_single_line_recovery_accepts_labelled_answer_among_runtime_noise():
    raw = "Loading model\nTranslation: This is a test.\nExiting..."
    assert clean_single_line_output(raw, 69) == "This is a test."


def test_single_line_recovery_accepts_one_useful_line_after_known_runtime_noise():
    raw = "Loading model\nThis is a test.\nExiting..."
    assert clean_single_line_output(raw, 69) == "This is a test."
