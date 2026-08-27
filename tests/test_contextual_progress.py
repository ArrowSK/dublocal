from __future__ import annotations

import dublocal.contextual_progress as contextual_progress
from dublocal.timeline import Segment


def test_translate_chunk_retries_malformed_structured_output(monkeypatch):
    targets = [
        Segment(index=1, start_ms=0, end_ms=1000, text="Hello."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="How are you?"),
    ]
    replies = iter(
        [
            "This is not JSON at all.",
            '[{"id":1,"text":"Привет."},{"id":2,"text":"Как дела?"}]',
        ]
    )
    calls: list[str] = []

    def fake_run(prompt: str, *, max_output_tokens: int) -> str:
        calls.append(prompt)
        return next(replies)

    monkeypatch.setattr(contextual_progress, "_run_llama", fake_run)

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
    assert len(calls) == 2
    assert "STRICT JSON" in calls[1]
    assert "natural Russian" in calls[1]
