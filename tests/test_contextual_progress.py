from __future__ import annotations

import dublocal.contextual_progress as contextual_progress
from dublocal.timeline import Segment


def _targets() -> list[Segment]:
    return [
        Segment(index=1, start_ms=0, end_ms=1000, text="Hello."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="How are you?"),
    ]


class FakeSession:
    def __init__(self, replies: list[str]):
        self.replies = iter(replies)
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, max_output_tokens: int) -> str:
        self.prompts.append(prompt)
        return next(self.replies)


def test_translate_chunk_accepts_clean_protocol_output():
    session = FakeSession(
        [
            "DUBLOCAL_TRANSLATION_BEGIN\n"
            "[1] - Привет.\n"
            "[2] - Как дела?\n"
            "DUBLOCAL_TRANSLATION_END"
        ]
    )

    result = contextual_progress._translate_chunk(
        session,
        "original prompt",
        _targets(),
        "ru",
        max_output_tokens=512,
        chunk_number=1,
        total_chunks=1,
        progress_callback=None,
    )

    assert result == ["Привет.", "Как дела?"]
    assert len(session.prompts) == 1


def test_translate_chunk_recovers_only_missing_ids_with_full_context():
    session = FakeSession(
        [
            "DUBLOCAL_TRANSLATION_BEGIN\n[1] - Привет.\nDUBLOCAL_TRANSLATION_END",
            "DUBLOCAL_TRANSLATION_BEGIN\n[2] - Как дела?\nDUBLOCAL_TRANSLATION_END",
        ]
    )

    result = contextual_progress._translate_chunk(
        session,
        "original prompt with programme context",
        _targets(),
        "ru",
        max_output_tokens=512,
        chunk_number=3,
        total_chunks=3,
        progress_callback=None,
    )

    assert result == ["Привет.", "Как дела?"]
    assert len(session.prompts) == 2
    assert "original prompt with programme context" in session.prompts[1]
    assert "subtitle [2]" in session.prompts[1]


def test_short_programme_is_packed_into_one_translation_chunk():
    segments = [
        Segment(index=i + 1, start_ms=i * 1000, end_ms=(i + 1) * 1000, text="Short lyric line")
        for i in range(33)
    ]
    assert contextual_progress._chunk_ranges(segments, 4096) == [(0, 33)]
