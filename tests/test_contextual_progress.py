from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dublocal.contextual_progress as contextual_progress
from dublocal.timeline import Segment, parse_srt


def _targets() -> list[Segment]:
    return [
        Segment(index=1, start_ms=0, end_ms=1000, text="Hello."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="How are you?"),
    ]


class FakeRuntime:
    mode = "fake-server"

    def __init__(self, replies: list[str]):
        self.replies = iter(replies)
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, max_output_tokens: int) -> str:
        self.prompts.append(prompt)
        return next(self.replies)


def test_translate_chunk_recovers_malformed_primary_output():
    runtime = FakeRuntime(
        [
            "This is not aligned output.",
            "[1] - Привет.\n[2] - Как дела?\n",
        ]
    )
    result = contextual_progress._translate_chunk_with_recovery(
        runtime,
        "original prompt",
        _targets(),
        "ru",
        max_output_tokens=512,
        chunk_number=1,
        total_chunks=3,
        progress_callback=None,
    )
    assert result == ["Привет.", "Как дела?"]
    assert len(runtime.prompts) == 2
    assert "Do not output JSON" in runtime.prompts[1]
    assert "natural Russian" in runtime.prompts[1]


def test_translate_chunk_recovers_only_missing_ids_individually():
    runtime = FakeRuntime(
        [
            "not structured",
            "[1] - Привет.\n",  # whole-chunk recovery omitted subtitle 2
            "[2] - Как дела?",
        ]
    )
    result = contextual_progress._translate_chunk_with_recovery(
        runtime,
        "original prompt with programme context",
        _targets(),
        "ru",
        max_output_tokens=512,
        chunk_number=3,
        total_chunks=3,
        progress_callback=None,
    )
    assert result == ["Привет.", "Как дела?"]
    assert len(runtime.prompts) == 3
    assert "subtitle [2]" in runtime.prompts[2]
    assert "original prompt with programme context" in runtime.prompts[2]


def test_wrong_script_is_recovered_instead_of_written():
    runtime = FakeRuntime(
        [
            "[1] - Привет.\n[2] - Где находится我的心?",
            "[1] - Привет.\n[2] - Где моё сердце?",
        ]
    )
    result = contextual_progress._translate_chunk_with_recovery(
        runtime,
        "context",
        _targets(),
        "ru",
        max_output_tokens=512,
        chunk_number=1,
        total_chunks=1,
        progress_callback=None,
    )
    assert result == ["Привет.", "Где моё сердце?"]


def test_contextual_translation_preserves_standalone_tags(monkeypatch, tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n[MUSIC]\n\n"
        "2\n00:00:01,000 --> 00:00:03,000\nI feel like one.\n",
        encoding="utf-8",
    )

    class Runtime:
        mode = "fake-server"

        def __init__(self, model_key: str = "8b"):
            assert model_key == "8b"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def generate(self, prompt: str, *, max_output_tokens: int) -> str:
            assert "[MUSIC]" not in prompt.split("TARGET LINES — translate these and only these:", 1)[1]
            return "[2] - Я чувствую себя таким."

    monkeypatch.setattr(contextual_progress, "ContextualRuntime", Runtime)
    monkeypatch.setattr(contextual_progress, "_llama_command", lambda: ["llama-cli"])
    monkeypatch.setattr(contextual_progress, "contextual_model_valid", lambda key: key == "8b")
    monkeypatch.setattr(
        contextual_progress,
        "active_recommendation",
        lambda: SimpleNamespace(model_key="8b", review=False, context_cap_tokens=16384),
    )

    result = contextual_progress.translate_srt_contextual_with_progress(
        source,
        "en",
        "ru",
        review=False,
    )
    segments = parse_srt(result.srt_path.read_text(encoding="utf-8"))
    assert segments[0].text == "[MUSIC]"
    assert segments[1].text == "Я чувствую себя таким."
