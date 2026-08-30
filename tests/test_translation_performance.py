from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dublocal.contextual_progress as contextual_progress
import dublocal.contextual_runtime as contextual_runtime
import dublocal.translation_performance as performance
from dublocal.timeline import Segment, segments_to_srt


def _segments(count: int, *, duration_ms: int, text: str = "Hi") -> list[Segment]:
    step = max(1, duration_ms // count)
    result: list[Segment] = []
    for position in range(count):
        start = position * step
        end = duration_ms if position == count - 1 else (position + 1) * step
        result.append(Segment(index=position + 1, start_ms=start, end_ms=end, text=text))
    return result


def test_dense_tiny_captions_get_larger_optimistic_batches():
    fragments = _segments(320, duration_ms=9 * 60_000, text="Okay")

    assert performance.adaptive_batch_max("8b", fragments) == 96
    assert performance.adaptive_batch_max("4b", fragments) == 72


def test_normal_sentence_subtitles_keep_established_batch_limits():
    sentences = _segments(
        90,
        duration_ms=9 * 60_000,
        text="This is a normal sentence-sized subtitle with enough context to translate.",
    )

    assert performance.adaptive_batch_max("8b", sentences) == 48
    assert performance.adaptive_batch_max("4b", sentences) == 36


def test_short_programme_runtime_context_matches_actual_prompt_budget():
    timeline = _segments(320, duration_ms=9 * 60_000, text="Okay")
    plan = contextual_progress.context_plan(timeline)

    effective = performance.effective_context_cap(timeline, 16_384)

    assert effective == plan.input_budget_tokens
    assert effective < 16_384
    assert effective >= 4096


def test_cache_reuse_is_added_only_when_server_reports_support(monkeypatch):
    monkeypatch.setattr(contextual_runtime, "_llama_server_command", lambda: ["llama-server"])
    monkeypatch.setattr(performance, "_server_supports_cache_reuse", lambda _command: True)

    runtime = performance.CachedContextualRuntime(model_key="8b", context_tokens=8192)

    assert runtime._server_command == ["llama-server", "--cache-reuse", "64"]
    assert "prompt reuse 64t" in runtime.mode


def test_wrapper_applies_dense_batch_and_context_only_during_call(monkeypatch, tmp_path: Path):
    timeline = _segments(80, duration_ms=2 * 60_000, text="Yes")
    subtitle = tmp_path / "captions.srt"
    subtitle.write_text(segments_to_srt(timeline), encoding="utf-8")
    seen: dict[str, int] = {}

    monkeypatch.setattr(
        contextual_progress,
        "active_recommendation",
        lambda: SimpleNamespace(model_key="8b", context_cap_tokens=16_384),
    )

    def fake_translate(*args, **kwargs):
        seen["context"] = int(kwargs["context_cap_tokens"])
        seen["batch"] = int(contextual_progress._ADAPTIVE_BATCH_MAX_8B)
        return "ok"

    monkeypatch.setattr(performance, "_ORIGINAL_TRANSLATE", fake_translate)
    original_batch = contextual_progress._ADAPTIVE_BATCH_MAX_8B

    result = performance.translate_srt_contextual_optimized(
        subtitle,
        "hu",
        "en",
    )

    assert result == "ok"
    assert seen["batch"] == 96
    assert seen["context"] == performance.effective_context_cap(timeline, 16_384)
    assert contextual_progress._ADAPTIVE_BATCH_MAX_8B == original_batch
