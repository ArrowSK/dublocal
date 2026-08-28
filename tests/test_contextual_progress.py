from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dublocal.contextual_progress as contextual_progress
from dublocal.timeline import Segment, parse_srt
from dublocal.translation import TranslatedSegment
from dublocal.translation_cache import CachedTranslation


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


def test_translate_chunk_recovers_missing_ids_in_one_batch():
    runtime = FakeRuntime(
        [
            "not structured",
            "[1] - Привет.\n",  # whole-chunk repair omitted subtitle 2
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
    assert "MISSING SUBTITLE RECOVERY" in runtime.prompts[2]
    assert "Missing IDs: 2" in runtime.prompts[2]
    assert "original prompt with programme context" in runtime.prompts[2]


def test_many_missing_subtitles_do_not_trigger_one_model_call_per_line():
    targets = [
        Segment(index=index, start_ms=index * 1000, end_ms=(index + 1) * 1000, text=f"Line {index}.")
        for index in range(1, 11)
    ]
    primary = "\n".join(f"[{index}] - Translation {index}." for index in range(1, 4))
    recovered_batch = "\n".join(f"[{index}] - Translation {index}." for index in range(4, 11))
    runtime = FakeRuntime([primary, recovered_batch])

    result = contextual_progress._translate_chunk_with_recovery(
        runtime,
        "large original context",
        targets,
        "en",
        max_output_tokens=1024,
        chunk_number=1,
        total_chunks=1,
        progress_callback=None,
    )

    assert result == [f"Translation {index}." for index in range(1, 11)]
    assert len(runtime.prompts) == 2
    assert "Missing IDs: 4, 5, 6, 7, 8, 9, 10" in runtime.prompts[1]


def test_wrong_script_is_recovered_instead_of_written():
    runtime = FakeRuntime(
        [
            "[1] - Привет.\n[2] - Где находится我的心?",
            "[2] - Где моё сердце?",
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
    assert len(runtime.prompts) == 2
    assert "Missing IDs: 2" in runtime.prompts[1]


def test_auto_language_parser_accepts_code_label_and_json():
    assert contextual_progress._parse_detected_language("en") == "en"
    assert contextual_progress._parse_detected_language("English") == "en"
    assert contextual_progress._parse_detected_language('{"language":"es"}') == "es"


def test_contextual_translation_auto_detects_source_with_same_runtime(monkeypatch, tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHello, how are you?\n",
        encoding="utf-8",
    )

    class Runtime:
        mode = "fake-server"
        instances = 0
        prompts: list[str] = []

        def __init__(self, model_key: str = "8b", context_tokens: int | None = None):
            Runtime.instances += 1
            assert model_key == "8b"
            assert context_tokens == 20480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def generate(self, prompt: str, *, max_output_tokens: int) -> str:
            Runtime.prompts.append(prompt)
            if "Identify the dominant human language" in prompt:
                return "English"
            return "[1] - Hola, ¿cómo estás?"

    monkeypatch.setattr(contextual_progress, "ContextualRuntime", Runtime)
    monkeypatch.setattr(contextual_progress, "load_translation_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(contextual_progress, "save_translation_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(contextual_progress, "_llama_command", lambda: ["llama-cli"])
    monkeypatch.setattr(contextual_progress, "contextual_model_valid", lambda key: key == "8b")
    monkeypatch.setattr(
        contextual_progress,
        "active_recommendation",
        lambda: SimpleNamespace(model_key="8b", review=False, context_cap_tokens=16384),
    )

    result = contextual_progress.translate_srt_contextual_with_progress(
        source,
        "auto",
        "es",
        review=False,
    )

    assert Runtime.instances == 1
    assert result.source_language == "en"
    assert result.target_language == "es"
    assert "English → Spanish" in result.route
    assert len(Runtime.prompts) == 2
    assert "Identify the dominant human language" in Runtime.prompts[0]
    assert "Translate the TARGET LINES from English" in Runtime.prompts[1]


def test_contextual_translation_preserves_standalone_tags(monkeypatch, tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n[MUSIC]\n\n"
        "2\n00:00:01,000 --> 00:00:03,000\nI feel like one.\n",
        encoding="utf-8",
    )

    class Runtime:
        mode = "fake-server"

        def __init__(self, model_key: str = "8b", context_tokens: int | None = None):
            assert model_key == "8b"
            assert context_tokens == 20480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def generate(self, prompt: str, *, max_output_tokens: int) -> str:
            assert "[MUSIC]" not in prompt.split("TARGET LINES — translate these and only these:", 1)[1]
            return "[2] - Я чувствую себя таким."

    monkeypatch.setattr(contextual_progress, "ContextualRuntime", Runtime)
    monkeypatch.setattr(contextual_progress, "load_translation_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(contextual_progress, "save_translation_cache", lambda *args, **kwargs: None)
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


def test_contextual_translation_cache_hit_skips_runtime_and_model_readiness(monkeypatch, tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHello there.\n",
        encoding="utf-8",
    )
    cached = CachedTranslation(
        segments=[TranslatedSegment(1, 0, 2000, "Hello there.", "Привет.")],
        source_language="en",
        target_language="ru",
        route="Qwen3 8B + review · English → Russian",
    )

    class RuntimeMustNotStart:
        def __init__(self, *args, **kwargs):
            raise AssertionError("cache hit must not load the translation runtime")

    monkeypatch.setattr(contextual_progress, "ContextualRuntime", RuntimeMustNotStart)
    monkeypatch.setattr(contextual_progress, "load_translation_cache", lambda *args, **kwargs: cached)
    monkeypatch.setattr(contextual_progress, "_llama_command", lambda: None)
    monkeypatch.setattr(contextual_progress, "contextual_model_valid", lambda key: False)
    monkeypatch.setattr(
        contextual_progress,
        "active_recommendation",
        lambda: SimpleNamespace(model_key="8b", review=True, context_cap_tokens=24576),
    )

    result = contextual_progress.translate_srt_contextual_with_progress(source, "en", "ru")
    assert result.srt_path.is_file()
    assert result.source_language == "en"
    assert [item.translated_text for item in result.segments] == ["Привет."]
    assert "cache hit" in result.route


def test_successful_contextual_translation_is_saved_after_validation(monkeypatch, tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHello there.\n",
        encoding="utf-8",
    )
    saved: dict[str, object] = {}

    class Runtime:
        mode = "fake-server"

        def __init__(self, model_key: str = "8b", context_tokens: int | None = None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def generate(self, prompt: str, *, max_output_tokens: int) -> str:
            return "[1] - Привет."

    def remember(key, translated, **kwargs):
        saved["key"] = key
        saved["translated"] = list(translated)
        saved.update(kwargs)

    monkeypatch.setattr(contextual_progress, "ContextualRuntime", Runtime)
    monkeypatch.setattr(contextual_progress, "load_translation_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(contextual_progress, "save_translation_cache", remember)
    monkeypatch.setattr(contextual_progress, "_llama_command", lambda: ["llama-cli"])
    monkeypatch.setattr(contextual_progress, "contextual_model_valid", lambda key: True)
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
    assert result.segments[0].translated_text == "Привет."
    assert saved["source_language"] == "en"
    assert saved["target_language"] == "ru"
    assert saved["translated"][0].translated_text == "Привет."
