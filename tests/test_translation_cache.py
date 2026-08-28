from __future__ import annotations

from pathlib import Path

import dublocal.translation_cache as cache
from dublocal.timeline import Segment
from dublocal.translation import TranslatedSegment


def _source() -> list[Segment]:
    return [
        Segment(1, 0, 1000, "Hello."),
        Segment(2, 1000, 2200, "How are you?"),
    ]


def _translated() -> list[TranslatedSegment]:
    return [
        TranslatedSegment(1, 0, 1000, "Hello.", "Привет."),
        TranslatedSegment(2, 1000, 2200, "How are you?", "Как дела?"),
    ]


def test_translation_cache_round_trip(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cache, "translation_cache_root", lambda: tmp_path)
    key = cache.translation_cache_key(
        "source srt",
        requested_source_language="en",
        target_language="ru",
        model_key="8b",
        model_revision="revision",
        model_sha256="sha",
        review=True,
        context_cap_tokens=24576,
        chunk_segments=48,
        input_budget_tokens=4096,
        prompt_version="v1",
    )
    cache.save_translation_cache(
        key,
        _translated(),
        source_language="en",
        target_language="ru",
        route="Qwen3 8B + review",
    )

    result = cache.load_translation_cache(key, _source(), target_language="ru")
    assert result is not None
    assert result.source_language == "en"
    assert result.target_language == "ru"
    assert result.route == "Qwen3 8B + review"
    assert [item.translated_text for item in result.segments] == ["Привет.", "Как дела?"]


def test_translation_cache_rejects_timing_mismatch(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cache, "translation_cache_root", lambda: tmp_path)
    key = "fixed-key"
    cache.save_translation_cache(
        key,
        _translated(),
        source_language="en",
        target_language="ru",
        route="route",
    )
    changed = [
        Segment(1, 0, 1100, "Hello."),
        Segment(2, 1100, 2200, "How are you?"),
    ]
    assert cache.load_translation_cache(key, changed, target_language="ru") is None


def test_translation_cache_key_invalidates_quality_policy_changes():
    common = dict(
        source_srt="source srt",
        requested_source_language="en",
        target_language="es",
        model_key="8b",
        model_revision="revision",
        model_sha256="sha",
        context_cap_tokens=24576,
        chunk_segments=48,
        input_budget_tokens=4096,
    )
    reviewed = cache.translation_cache_key(**common, review=True, prompt_version="v1")
    single = cache.translation_cache_key(**common, review=False, prompt_version="v1")
    changed_prompt = cache.translation_cache_key(**common, review=True, prompt_version="v2")
    assert reviewed != single
    assert reviewed != changed_prompt
