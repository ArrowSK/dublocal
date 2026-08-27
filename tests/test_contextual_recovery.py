from __future__ import annotations

import json

from dublocal.contextual_recovery import build_format_repair_prompt, recover_chunk_output
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


def test_repair_prompt_names_target_language_and_ids():
    prompt = build_format_repair_prompt("bad output", _targets(), "Russian")
    assert "natural Russian" in prompt
    assert "1, 2" in prompt
    assert "bad output" in prompt
    assert "STRICT JSON" in prompt
