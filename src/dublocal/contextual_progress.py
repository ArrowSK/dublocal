from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from .contextual_policy import build_translation_prompt, context_plan
from .contextual_recovery import (
    build_format_repair_prompt,
    build_single_line_recovery_prompt,
    clean_single_line_output,
    recover_chunk_output,
    recover_partial_output,
)
from .contextual_runtime import ContextualRuntime
from .contextual_translation import (
    ContextualTranslationMissingError,
    _llama_command,
    _new_job_dir,
    _registered_model_valid,
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
from .translation_quality import is_protected_caption_tag, validate_translation_text


ProgressCallback = Callable[[float, str], None]


def _validated_chunk(
    texts: Sequence[str],
    target_segments: Sequence[Segment],
    target_language: str,
) -> list[str]:
    return [
        validate_translation_text(
            text,
            target_language=target_language,
            segment_id=segment.index,
        )
        for segment, text in zip(target_segments, texts, strict=True)
    ]


def _translate_chunk_with_recovery(
    runtime: ContextualRuntime,
    prompt: str,
    target_segments: Sequence[Segment],
    target_language: str,
    *,
    max_output_tokens: int,
    chunk_number: int,
    total_chunks: int,
    progress_callback: ProgressCallback | None,
) -> list[str]:
    raw = runtime.generate(prompt, max_output_tokens=max_output_tokens)
    try:
        return _validated_chunk(
            recover_chunk_output(raw, target_segments),
            target_segments,
            target_language,
        )
    except DubLocalError:
        if progress_callback:
            progress_callback(
                max(0.02, min(0.95, (chunk_number - 0.4) / max(1, total_chunks) * 0.94 + 0.02)),
                f"Recovering output for chunk {chunk_number}/{total_chunks}",
            )

        target_label = TRANSLATION_LANGUAGES[target_language]["label"]
        repair_prompt = build_format_repair_prompt(
            raw,
            target_segments,
            target_label,
        )
        repaired = runtime.generate(
            repair_prompt,
            max_output_tokens=max(512, max_output_tokens),
        )
        try:
            return _validated_chunk(
                recover_chunk_output(repaired, target_segments),
                target_segments,
                target_language,
            )
        except DubLocalError:
            pass

        recovered = recover_partial_output(raw, target_segments)
        recovered.update(recover_partial_output(repaired, target_segments))

        # Discard any recovered line that contains runtime/UI noise or a clearly wrong script.
        for segment in target_segments:
            if segment.index not in recovered:
                continue
            try:
                recovered[segment.index] = validate_translation_text(
                    recovered[segment.index],
                    target_language=target_language,
                    segment_id=segment.index,
                )
            except DubLocalError:
                recovered.pop(segment.index, None)

        missing = [segment for segment in target_segments if segment.index not in recovered]
        for position, segment in enumerate(missing, start=1):
            if progress_callback:
                base = max(
                    0.02,
                    min(0.95, (chunk_number - 0.25) / max(1, total_chunks) * 0.94 + 0.02),
                )
                progress_callback(
                    base,
                    f"Recovering subtitle {position}/{len(missing)} in chunk {chunk_number}/{total_chunks}",
                )

            single_prompt = build_single_line_recovery_prompt(
                prompt,
                segment,
                target_label,
                repaired,
            )
            single_raw = runtime.generate(
                single_prompt,
                max_output_tokens=max(128, min(512, estimate_tokens(segment.text) * 4 + 96)),
            )
            partial = recover_partial_output(single_raw, [segment])
            if segment.index in partial:
                candidate = partial[segment.index]
            else:
                candidate = clean_single_line_output(single_raw, segment.index)
            recovered[segment.index] = validate_translation_text(
                candidate,
                target_language=target_language,
                segment_id=segment.index,
            )

        expected = [segment.index for segment in target_segments]
        if any(index not in recovered for index in expected):
            still_missing = [index for index in expected if index not in recovered]
            raise DubLocalError(
                "Contextual translator could not recover all required subtitle IDs "
                f"for chunk {chunk_number}/{total_chunks} (missing={still_missing[:5]}). "
                "DubLocal stopped instead of writing a corrupted SRT."
            )
        return [recovered[index] for index in expected]


def translate_srt_contextual_with_progress(
    subtitle_path: str | Path,
    source_language: str,
    target_language: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> TranslationResult:
    """Contextual translation with protected cue tags and one reused local model session."""

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
    protected_count = sum(1 for segment in segments if is_protected_caption_tag(segment.text))
    needs_model = protected_count < len(segments)
    runtime_mode = "not needed"

    if progress_callback:
        progress_callback(
            0.02,
            f"Preparing {total_chunks} contextual translation chunk(s) · {protected_count} protected tag(s)",
        )

    runtime: ContextualRuntime | None = None
    try:
        if needs_model:
            if progress_callback:
                progress_callback(0.03, "Loading local Qwen model once for this translation")
            runtime = ContextualRuntime().__enter__()
            runtime_mode = runtime.mode

        for chunk_number, start in enumerate(starts, start=1):
            end = min(len(segments), start + plan.chunk_segments)
            target_segments = segments[start:end]
            model_targets = [
                segment for segment in target_segments if not is_protected_caption_tag(segment.text)
            ]
            translated_map: dict[int, str] = {}

            if model_targets:
                assert runtime is not None
                prompt = build_translation_prompt(
                    segments,
                    start,
                    end,
                    source,
                    target,
                    translated,
                    plan,
                )
                target_text = "\n".join(segment.text for segment in model_targets)
                max_output_tokens = max(512, estimate_tokens(target_text) * 2 + 256)
                chunk = _translate_chunk_with_recovery(
                    runtime,
                    prompt,
                    model_targets,
                    target,
                    max_output_tokens=max_output_tokens,
                    chunk_number=chunk_number,
                    total_chunks=total_chunks,
                    progress_callback=progress_callback,
                )
                translated_map = {
                    segment.index: text
                    for segment, text in zip(model_targets, chunk, strict=True)
                }

            for segment in target_segments:
                text = (
                    segment.text
                    if is_protected_caption_tag(segment.text)
                    else translated_map[segment.index]
                )
                translated.append(
                    TranslatedSegment(
                        index=segment.index,
                        start_ms=segment.start_ms,
                        end_ms=segment.end_ms,
                        source_text=segment.text,
                        translated_text=text,
                    )
                )

            if progress_callback:
                progress_callback(
                    min(0.96, chunk_number / total_chunks * 0.94 + 0.02),
                    f"Translated context chunk {chunk_number}/{total_chunks}",
                )
    finally:
        if runtime is not None:
            runtime.__exit__(None, None, None)

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
        f"{TRANSLATION_LANGUAGES[target]['label']} · {plan.input_budget_tokens}-token context budget · "
        f"{runtime_mode}"
    )
    return TranslationResult(
        srt_path=output,
        segments=translated,
        source_language=source,
        target_language=target,
        route=route,
    )
