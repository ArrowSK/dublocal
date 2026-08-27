from __future__ import annotations

import dublocal.contextual_progress as contextual_progress
from dublocal.contextual_recovery import build_format_repair_prompt, recover_chunk_output
from dublocal.timeline import Segment


def _targets() -> list[Segment]:
    return [
        Segment(index=1, start_ms=0, end_ms=1000, text="Hello."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="How are you?"),
    ]


def test_plain_text_recovery_protocol_preserves_alignment():
    assert recover_chunk_output(
        "[1] - Привет.\n[2] - Как ты?\n",
        _targets(),
    ) == ["Привет.", "Как ты?"]


def test_repair_prompt_uses_non_json_line_protocol():
    prompt = build_format_repair_prompt("bad output", _targets(), "Russian")
    assert "[ID] - translated text" in prompt
    assert "Do not output JSON" in prompt
    assert "Required subtitle ids, exactly once and in this order: 1, 2" in prompt


def test_chunk_falls_back_when_json_schema_output_is_malformed(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        contextual_progress,
        "_run_llama",
        lambda prompt, max_output_tokens: "this is not valid structured output",
    )

    def fake_unconstrained(prompt: str, *, max_output_tokens: int) -> str:
        calls.append(prompt)
        return "[1] - Привет.\n[2] - Как ты?\n"

    monkeypatch.setattr(
        contextual_progress,
        "run_llama_unconstrained",
        fake_unconstrained,
    )

    result = contextual_progress._translate_chunk_with_recovery(
        "contextual prompt",
        _targets(),
        "ru",
        max_output_tokens=512,
        chunk_number=1,
        total_chunks=1,
        progress_callback=None,
    )

    assert result == ["Привет.", "Как ты?"]
    assert calls
    assert "Do not output JSON" in calls[0]
