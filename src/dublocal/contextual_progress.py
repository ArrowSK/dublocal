from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from .contextual_protocol import (
    build_line_translation_prompt,
    parse_line_translation,
    parse_partial_line_translation,
)
from .contextual_runtime import ContextualLlamaSession
from .contextual_translation import (
    ContextualTranslationMissingError,
    _llama_command,
    _new_job_dir,
    _registered_model_valid,
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


def _chunk_ranges(segments: Sequence[Segment], input_budget_tokens: int) -> list[tuple[int, int]]:
    """Pack short material into fewer model calls while keeping long outputs bounded."""

    if not segments:
        return []

    target_token_cap = min(2400, max(1200, input_budget_tokens // 2))
    max_segments = 64
    ranges: list[tuple[int, int]] = []
    start = 0
    used = 0

    for position, segment in enumerate(segments):
        cost = estimate_tokens(segment.text) + 6
        if position > start and (used + cost > target_token_cap or position - start >= max_segments):
            ranges.append((start, position))
            start = position
            used = 0
        used += cost

    ranges.append((start, len(segments)))
    return ranges


def _single_id_prompt(
    original_prompt: str,
    segment: Segment,
    target_language_label: str,
) -> str:
    return (
        original_prompt.rstrip()
        + "\n\nRECOVERY TASK:\n"
        + f"The previous response omitted or corrupted subtitle [{segment.index}]. Use all context above and translate ONLY that subtitle into natural {target_language_label}.\n"
        + f"Source text: {segment.text}\n"
        + "Return exactly this protocol and nothing else:\n"
        + "DUBLOCAL_TRANSLATION_BEGIN\n"
        + f"[{segment.index}] - translated text\n"
        + "DUBLOCAL_TRANSLATION_END\n"
    )


def _translate_chunk(
    session: ContextualLlamaSession,
    prompt: str,
    target_segments: Sequence[Segment],
    target_language: str,
    *,
    max_output_tokens: int,
    chunk_number: int,
    total_chunks: int,
    progress_callback: ProgressCallback | None,
) -> list[str]:
    raw = session.complete(prompt, max_output_tokens=max_output_tokens)
    try:
        return parse_line_translation(raw, target_segments)
    except DubLocalError:
        recovered = parse_partial_line_translation(raw, target_segments)

    missing = [segment for segment in target_segments if segment.index not in recovered]
    target_label = TRANSLATION_LANGUAGES[target_language]["label"]

    for position, segment in enumerate(missing, start=1):
        if progress_callback:
            fraction = max(
                0.03,
                min(0.95, ((chunk_number - 1) + position / max(1, len(missing))) / max(1, total_chunks)),
            )
            progress_callback(
                fraction,
                f"Recovering subtitle {position}/{len(missing)} in chunk {chunk_number}/{total_chunks}",
            )
        single_raw = session.complete(
            _single_id_prompt(prompt, segment, target_label),
            max_output_tokens=max(128, min(384, estimate_tokens(segment.text) * 4 + 96)),
        )
        recovered[segment.index] = parse_line_translation(single_raw, [segment])[0]

    expected = [segment.index for segment in target_segments]
    still_missing = [index for index in expected if index not in recovered]
    if still_missing:
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
    """Translate locally with one persistent llama.cpp model session per job."""

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
    ranges = _chunk_ranges(segments, plan.input_budget_tokens)
    total_chunks = max(1, len(ranges))
    translated: list[TranslatedSegment] = []

    if progress_callback:
        progress_callback(0.02, f"Loading contextual model once for {total_chunks} translation chunk(s)")

    with ContextualLlamaSession() as session:
        if progress_callback:
            progress_callback(0.06, "Contextual model ready")

        for chunk_number, (start, end) in enumerate(ranges, start=1):
            target_segments = segments[start:end]
            prompt = build_line_translation_prompt(
                segments,
                start,
                end,
                source,
                target,
                translated,
                plan,
            )
            target_text = "\n".join(segment.text for segment in target_segments)
            max_output_tokens = max(512, estimate_tokens(target_text) * 2 + 256)
            chunk = _translate_chunk(
                session,
                prompt,
                target_segments,
                target,
                max_output_tokens=max_output_tokens,
                chunk_number=chunk_number,
                total_chunks=total_chunks,
                progress_callback=progress_callback,
            )
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
                    min(0.96, chunk_number / total_chunks * 0.90 + 0.06),
                    f"Translated context chunk {chunk_number}/{total_chunks}",
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
        f"{TRANSLATION_LANGUAGES[target]['label']} · {plan.input_budget_tokens}-token context budget · "
        f"persistent llama.cpp session · {total_chunks} chunk(s)"
    )
    return TranslationResult(
        srt_path=output,
        segments=translated,
        source_language=source,
        target_language=target,
        route=route,
    )
