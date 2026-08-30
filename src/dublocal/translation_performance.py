from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Sequence

from . import contextual_progress
from .contextual_runtime import ContextualRuntime as _BaseContextualRuntime
from .contextual_translation import estimate_tokens
from .timeline import Segment, parse_srt
from .translation_quality import is_protected_caption_tag


_INSTALLED = False
_PATCH_LOCK = threading.RLock()
_CACHE_REUSE_TOKENS = 64
_SERVER_OPTION_CACHE: dict[tuple[str, ...], bool] = {}
_ORIGINAL_TRANSLATE = contextual_progress.translate_srt_contextual_with_progress


def _dialogue_segments(segments: Sequence[Segment]) -> list[Segment]:
    return [
        segment
        for segment in segments
        if segment.text.strip() and not is_protected_caption_tag(segment.text)
    ]


def _caption_density(segments: Sequence[Segment]) -> tuple[float, float, int]:
    dialogue = _dialogue_segments(segments)
    if not dialogue:
        return 0.0, 0.0, 0
    duration_ms = max((segment.end_ms for segment in segments), default=0)
    minutes = max(duration_ms / 60_000.0, 1.0 / 60.0)
    costs = [estimate_tokens(segment.text) for segment in dialogue]
    return len(dialogue) / minutes, sum(costs) / len(costs), max(costs)


def adaptive_batch_max(model_key: str, segments: Sequence[Segment]) -> int:
    """Use larger first attempts only for genuinely fragmented, short-caption timelines.

    Large batches reduce repeated prompt prefill substantially on YouTube-style rolling
    captions. The existing alignment validator and 1/2-size fallback remain authoritative:
    a 96-line attempt that does not preserve IDs is retried as 48, then 24, then 12.
    Normal sentence-sized subtitles retain the established 48/36 limits.
    """

    base = 48 if model_key == "8b" else 36
    per_minute, average_tokens, largest_tokens = _caption_density(segments)

    if per_minute >= 30.0 and average_tokens <= 8.0 and largest_tokens <= 32:
        return 96 if model_key == "8b" else 72
    if per_minute >= 20.0 and average_tokens <= 12.0 and largest_tokens <= 48:
        return 72 if model_key == "8b" else 54
    return base


def effective_context_cap(segments: Sequence[Segment], recommendation_cap: int) -> int:
    """Allocate only the context the current programme can actually use.

    The normal planner already decides the source-context budget from programme length.
    Keeping the runtime at a blanket 16k/24k input cap for a short programme does not
    expose more context to the model; it only allocates a larger KV cache. The runtime
    adds its existing 4096-token generation/headroom margin on top of this value.
    """

    plan = contextual_progress.context_plan(segments)
    return max(4096, min(int(recommendation_cap), int(plan.input_budget_tokens)))


def _server_supports_cache_reuse(command: Sequence[str]) -> bool:
    key = tuple(str(item) for item in command)
    cached = _SERVER_OPTION_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        result = subprocess.run(
            [*key, "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        supported = "--cache-reuse" in f"{result.stdout}\n{result.stderr}"
    except (OSError, subprocess.TimeoutExpired):
        supported = False
    _SERVER_OPTION_CACHE[key] = supported
    return supported


class CachedContextualRuntime(_BaseContextualRuntime):
    """Contextual runtime with exact llama.cpp prompt-chunk reuse when supported."""

    def __init__(self, model_key: str = "8b", context_tokens: int | None = None) -> None:
        super().__init__(model_key=model_key, context_tokens=context_tokens)
        if self._server_command and _server_supports_cache_reuse(self._server_command):
            self._server_command = [
                *self._server_command,
                "--cache-reuse",
                str(_CACHE_REUSE_TOKENS),
            ]
            self.mode += f" · prompt reuse {_CACHE_REUSE_TOKENS}t"


def translate_srt_contextual_optimized(
    subtitle_path: str | Path,
    source_language: str,
    target_language: str,
    *,
    review: bool | None = None,
    model_key: str | None = None,
    context_cap_tokens: int | None = None,
    progress_callback=None,
):
    """Preserve the translation model/quality policy while removing avoidable work."""

    path = Path(subtitle_path).expanduser().resolve()
    segments: list[Segment] = []
    if path.is_file() and path.suffix.lower() == ".srt":
        try:
            segments = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            segments = []

    recommendation = contextual_progress.active_recommendation()
    selected_model_key = model_key or recommendation.model_key

    # Only tune DubLocal's native llama.cpp runtime. Tests, library callers and future
    # custom runtimes may deliberately replace ContextualRuntime and can have different
    # context/batch semantics; preserving that hook is part of the compatibility contract.
    native_runtime = contextual_progress.ContextualRuntime is _BaseContextualRuntime
    selected_context_cap = context_cap_tokens
    if selected_context_cap is None and segments and native_runtime:
        selected_context_cap = effective_context_cap(
            segments,
            recommendation.context_cap_tokens,
        )

    selected_batch_max = (
        adaptive_batch_max(selected_model_key, segments)
        if segments and native_runtime
        else None
    )

    # The UI queue is single-job, but protect library/direct callers too because the
    # established translator reads these compatibility constants at call time.
    with _PATCH_LOCK:
        previous_4b = contextual_progress._ADAPTIVE_BATCH_MAX_4B
        previous_8b = contextual_progress._ADAPTIVE_BATCH_MAX_8B
        previous_runtime = contextual_progress.ContextualRuntime
        if selected_batch_max is not None:
            if selected_model_key == "8b":
                contextual_progress._ADAPTIVE_BATCH_MAX_8B = selected_batch_max
            else:
                contextual_progress._ADAPTIVE_BATCH_MAX_4B = selected_batch_max
        if native_runtime:
            contextual_progress.ContextualRuntime = CachedContextualRuntime
        try:
            return _ORIGINAL_TRANSLATE(
                subtitle_path,
                source_language,
                target_language,
                review=review,
                model_key=model_key,
                context_cap_tokens=selected_context_cap,
                progress_callback=progress_callback,
            )
        finally:
            contextual_progress._ADAPTIVE_BATCH_MAX_4B = previous_4b
            contextual_progress._ADAPTIVE_BATCH_MAX_8B = previous_8b
            contextual_progress.ContextualRuntime = previous_runtime


def install_translation_performance_refinement() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    contextual_progress.translate_srt_contextual_with_progress = translate_srt_contextual_optimized
    _INSTALLED = True
