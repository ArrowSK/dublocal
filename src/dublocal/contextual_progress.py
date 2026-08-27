from __future__ import annotations

from pathlib import Path
from typing import Callable

from .contextual_translation import (
    ContextualTranslationMissingError,
    _llama_command,
    _new_job_dir,
    _parse_chunk_output,
    _registered_model_valid,
    _run_llama,
    build_translation_prompt,
    context_plan,
    estimate_tokens,
)
from .media import DubLocalError
from .timeline import Segment, parse_srt, segments_to_srt
from .translation import (
    TRANSLATION_LANGUAGES,
    TranslatedSegment,
    TranslationResult,
    normalise_language_code,
)


ProgressCallback = Callable[[float, str], None]


def translate_srt_contextual_with_progress(
    subtitle_path: str | Path,
    source_language: str,
    target_language: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> TranslationResult:
    """Contextual translation with real chunk-level progress updates."""

    path = Path(subtitle_path).expanduser().resolve()
    if not path.is_file():
        raise DubLocalError("The subtitle file is no longer available. Extract or transcribe it again.")
    if path.suffix.lower() != ".srt":
        raise DubLocalError("Contextual translation expects DubLocal's normalized SRT timeline.")

    source = normalise_language_code(source_language)
    target = normalise_language_code(target_language)
    if source not in TRANSLATION_LANGUAGES:
        raise DubLocalError("Choose the subtitle source language before contextual translation.")
    if target not in TRANSLATION_LANGUAGES:
        raise DubLocalError("Choose a supported translation target language.")
    if source == target:
        raise DubLocalError("Source and target languages are the same; no translation is needed.")
    if not _llama_command() or not _registered_model_valid():
        raise ContextualTranslationMissingError(
            "Contextual translation is not prepared. Open Settings → Model Manager → Contextual translation and click Prepare / verify."
        )

    try:
        segments = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not read the subtitle timeline: {exc}") from exc
    if not segments:
        raise DubLocalError("The subtitle file contains no timed text to translate.")

    plan = context_plan(segments)
    starts = list(range(0, len(segments), plan.chunk_segments))
    total_chunks = max(1, len(starts))
    translated: list[TranslatedSegment] = []

    if progress_callback:
        progress_callback(0.02, f"Preparing {total_chunks} contextual translation chunk(s)")

    for chunk_number, start in enumerate(starts, start=1):
        end = min(len(segments), start + plan.chunk_segments)
        target_segments = segments[start:end]
        prompt = build_translation_prompt(
            segments,
            start,
            end,
            source,
            target,
            translated,
            plan,
        )
        target_text = "\n".join(segment.text for segment in target_segments)
        raw = _run_llama(
            prompt,
            max_output_tokens=max(512, estimate_tokens(target_text) * 2 + 256),
        )
        chunk = _parse_chunk_output(raw, target_segments)
        translated.extend(
            TranslatedSegment(
                index=segment.index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                source_text=segment.text,
                translated_text=text,
            )
            for segment, text in zip(target_segments, chunk, strict=True)
        )
        if progress_callback:
            progress_callback(
                min(0.96, chunk_number / total_chunks * 0.94 + 0.02),
                f"Translating context chunk {chunk_number}/{total_chunks}",
            )

    output_dir = _new_job_dir("contextual-translation")
    output = output_dir / f"captions.{target}.srt"
    output.write_text(
        segments_to_srt(
            [
                Segment(
                    index=item.index,
                    start_ms=item.start_ms,
                    end_ms=item.end_ms,
                    text=item.translated_text,
                )
                for item in translated
            ]
        ),
        encoding="utf-8",
    )
    if progress_callback:
        progress_callback(1.0, "Contextual translation complete")

    route = (
        f"Contextual Qwen3 · {TRANSLATION_LANGUAGES[source]['label']} → "
        f"{TRANSLATION_LANGUAGES[target]['label']} · {plan.input_budget_tokens}-token context budget"
    )
    return TranslationResult(
        srt_path=output,
        segments=translated,
        source_language=source,
        target_language=target,
        route=route,
    )
