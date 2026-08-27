from __future__ import annotations

import dublocal.contextual_progress as contextual_progress
from dublocal.timeline import Segment


def _targets() -> list[Segment]:
    return [
        Segment(index=1, start_ms=0, end_ms=1000, text="Hello."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="How are you?"),
    ]


def test_translate_chunk_retries_malformed_structured_output(monkeypatch):
    targets = _targets()
    primary_calls: list[str] = []
    recovery_calls: list[str] = []

    def fake_primary(prompt: str, *, max_output_tokens: int) -> str:
        primary_calls.append(prompt)
        return "This is not JSON at all."

    def fake_recovery(prompt: str, *, max_output_tokens: int) -> str:
        recovery_calls.append(prompt)
        return "[1] - Привет.\n[2] - Как дела?\n"

    monkeypatch.setattr(contextual_progress, "_run_llama", fake_primary)
    monkeypatch.setattr(contextual_progress, "run_llama_unconstrained", fake_recovery)

    result = contextual_progress._translate_chunk_with_recovery(
        "original prompt",
        targets,
        "ru",
        max_output_tokens=512,
        chunk_number=1,
        total_chunks=3,
        progress_callback=None,
    )

    assert result == ["Привет.", "Как дела?"]
    assert len(primary_calls) == 1
    assert len(recovery_calls) == 1
    assert "Do not output JSON" in recovery_calls[0]
    assert "natural Russian" in recovery_calls[0]


def test_translate_chunk_recovers_only_missing_ids_individually(monkeypatch):
    targets = _targets()
    calls: list[str] = []

    def fake_primary(prompt: str, *, max_output_tokens: int) -> str:
        return "not structured"

    def fake_recovery(prompt: str, *, max_output_tokens: int) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return "[1] - Привет.\n"  # chunk recovery omitted subtitle 2
        assert "subtitle [2]" in prompt
        assert "original prompt" in prompt  # full contextual prompt is retained
        return "Как дела?"

    monkeypatch.setattr(contextual_progress, "_run_llama", fake_primary)
    monkeypatch.setattr(contextual_progress, "run_llama_unconstrained", fake_recovery)

    result = contextual_progress._translate_chunk_with_recovery(
        "original prompt with programme context",
        targets,
        "ru",
        max_output_tokens=512,
        chunk_number=3,
        total_chunks=3,
        progress_callback=None,
    )

    assert result == ["Привет.", "Как дела?"]
    assert len(calls) == 2
