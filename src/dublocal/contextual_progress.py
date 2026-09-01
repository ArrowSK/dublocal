from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Sequence

from .adaptive_contextual import active_recommendation, contextual_model_spec, contextual_model_valid
from .contextual_policy import (
    CONTEXTUAL_PROMPT_VERSION,
    build_review_prompt,
    build_translation_prompt,
    context_plan,
)
from .contextual_recovery import (
    build_format_repair_prompt,
    build_missing_recovery_prompt,
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
from .translation_cache import (
    CachedTranslation,
    load_translation_cache,
    save_translation_cache,
    translation_cache_key,
)
from .translation_quality import is_protected_caption_tag, validate_translation_text


ProgressCallback = Callable[[float, str], None]

_ADAPTIVE_BATCH_MIN = 12
_ADAPTIVE_BATCH_MAX_4B = 36
_ADAPTIVE_BATCH_MAX_8B = 48
_ADAPTIVE_CACHE_POLICY = "adaptive-production-2026-09-01.1"


@dataclass(slots=True)
class _AdaptiveBatchState:
    """Optimistically use large batches, shrinking only after an alignment failure."""

    current: int
    maximum: int
    minimum: int = _ADAPTIVE_BATCH_MIN
    clean_streak: int = 0
    split_count: int = 0

    def shrink(self, attempted_span: int) -> bool:
        if attempted_span <= self.minimum:
            return False
        smaller = max(self.minimum, attempted_span // 2)
        if smaller >= attempted_span:
            return False
        self.current = min(self.current, smaller)
        self.clean_streak = 0
        self.split_count += 1
        return True

    def mark_success(self, *, recovered: bool) -> None:
        if recovered:
            self.clean_streak = 0
            return
        self.clean_streak += 1
        if self.clean_streak >= 2 and self.current < self.maximum:
            self.current = min(self.maximum, self.current * 2)
            self.clean_streak = 0


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
    """Choose a larger optimistic batch only for dense, tiny caption fragments.

    The strict ID/script validator and adaptive half-size retry remain authoritative.
    Normal sentence-sized subtitles retain the established 48/36 limits.
    """

    base = _ADAPTIVE_BATCH_MAX_8B if model_key == "8b" else _ADAPTIVE_BATCH_MAX_4B
    per_minute, average_tokens, largest_tokens = _caption_density(segments)
    if per_minute >= 30.0 and average_tokens <= 8.0 and largest_tokens <= 32:
        return 96 if model_key == "8b" else 72
    if per_minute >= 20.0 and average_tokens <= 12.0 and largest_tokens <= 48:
        return 72 if model_key == "8b" else 54
    return base


def effective_context_cap(segments: Sequence[Segment], recommendation_cap: int) -> int:
    """Allocate the context budget the programme can actually use, not a hardware ceiling."""

    plan = context_plan(segments)
    return max(4096, min(int(recommendation_cap), int(plan.input_budget_tokens)))


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


def _validated_cached_translation(
    cached: CachedTranslation | None,
    source_segments: Sequence[Segment],
    target_language: str,
) -> CachedTranslation | None:
    """Accept only a complete cache entry that still passes current output guards."""

    if cached is None or len(cached.segments) != len(source_segments):
        return None
    source_language = normalise_language_code(cached.source_language)
    if source_language not in TRANSLATION_LANGUAGES or source_language == target_language:
        return None

    checked: list[TranslatedSegment] = []
    try:
        for source, item in zip(source_segments, cached.segments, strict=True):
            if (
                item.index != source.index
                or item.start_ms != source.start_ms
                or item.end_ms != source.end_ms
            ):
                return None
            if is_protected_caption_tag(source.text):
                if item.translated_text != source.text:
                    return None
                text = source.text
            else:
                text = validate_translation_text(
                    item.translated_text,
                    target_language=target_language,
                    segment_id=source.index,
                )
            checked.append(
                TranslatedSegment(
                    index=source.index,
                    start_ms=source.start_ms,
                    end_ms=source.end_ms,
                    source_text=source.text,
                    translated_text=text,
                )
            )
    except DubLocalError:
        return None

    return CachedTranslation(
        segments=checked,
        source_language=source_language,
        target_language=target_language,
        route=cached.route,
    )


def _write_translation_output(
    translated: Sequence[TranslatedSegment],
    target_language: str,
) -> Path:
    output_dir = _new_job_dir("contextual-translation")
    output = output_dir / f"captions.{target_language}.srt"
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
    return output


def _language_detection_sample(segments: Sequence[Segment]) -> str:
    """Build a compact dialogue-only sample for Auto source-language identification."""

    lines: list[str] = []
    characters = 0
    for segment in segments:
        if is_protected_caption_tag(segment.text):
            continue
        text = " ".join(segment.text.split()).strip()
        if not text:
            continue
        lines.append(text)
        characters += len(text)
        if len(lines) >= 80 or characters >= 6000:
            break
    return "\n".join(lines)


def _parse_detected_language(raw: str) -> str:
    """Accept a terse ISO code, label, or tiny JSON object from the local model."""

    text = (raw or "").strip()
    if not text:
        return "auto"

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        for key in ("language", "lang", "code"):
            candidate = normalise_language_code(str(payload.get(key) or ""))
            if candidate in TRANSLATION_LANGUAGES:
                return candidate

    compact = text.strip("`'\" \t\r\n").casefold()
    direct = normalise_language_code(compact)
    if direct in TRANSLATION_LANGUAGES:
        return direct

    for code, metadata in TRANSLATION_LANGUAGES.items():
        if compact == str(metadata["label"]).casefold():
            return code

    code_pattern = "|".join(re.escape(code) for code in TRANSLATION_LANGUAGES)
    match = re.search(rf"\b({code_pattern})\b", compact[:160])
    if match:
        return match.group(1)

    for code, metadata in TRANSLATION_LANGUAGES.items():
        if str(metadata["label"]).casefold() in compact[:160]:
            return code
    return "auto"


def _detect_source_language(runtime: ContextualRuntime, segments: Sequence[Segment]) -> str:
    sample = _language_detection_sample(segments)
    if not sample:
        raise DubLocalError(
            "Auto source-language detection found no dialogue text to identify. "
            "Choose From manually for this subtitle timeline."
        )

    allowed = ", ".join(TRANSLATION_LANGUAGES)
    prompt = (
        "/no_think\n"
        "Identify the dominant human language of the subtitle dialogue below.\n"
        f"Return exactly one ISO code from this list and nothing else: {allowed}.\n"
        "Ignore names, isolated foreign words, sound-effect tags and punctuation.\n\n"
        "SUBTITLE SAMPLE:\n"
        f"{sample}\n"
    )
    raw = runtime.generate(prompt, max_output_tokens=24)
    detected = _parse_detected_language(raw)
    if detected not in TRANSLATION_LANGUAGES:
        raise DubLocalError(
            "Auto source-language detection could not determine a supported language confidently. "
            "Choose From manually and retry."
        )
    return detected


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
    initial_raw: str | None = None,
) -> list[str]:
    """Translate one chunk and repair malformed output with bounded model calls."""

    raw = initial_raw if initial_raw is not None else runtime.generate(
        prompt,
        max_output_tokens=max_output_tokens,
    )
    try:
        return _validated_chunk(
            recover_chunk_output(raw, target_segments),
            target_segments,
            target_language,
        )
    except DubLocalError:
        pass

    target_label = TRANSLATION_LANGUAGES[target_language]["label"]
    recovered: dict[int, str] = {}

    def absorb(candidate_raw: str, candidates: Sequence[Segment]) -> None:
        partial = recover_partial_output(candidate_raw, candidates)
        for segment in candidates:
            if segment.index in recovered or segment.index not in partial:
                continue
            try:
                recovered[segment.index] = validate_translation_text(
                    partial[segment.index],
                    target_language=target_language,
                    segment_id=segment.index,
                )
            except DubLocalError:
                continue

    absorb(raw, target_segments)
    last_output = raw

    if not recovered:
        if progress_callback:
            progress_callback(
                max(0.02, min(0.88, (chunk_number - 0.4) / max(1, total_chunks) * 0.80 + 0.02)),
                f"Repairing output format for batch {chunk_number}/{total_chunks}",
            )
        repaired = runtime.generate(
            build_format_repair_prompt(raw, target_segments, target_label),
            max_output_tokens=max(512, max_output_tokens),
        )
        last_output = repaired
        try:
            return _validated_chunk(
                recover_chunk_output(repaired, target_segments),
                target_segments,
                target_language,
            )
        except DubLocalError:
            absorb(repaired, target_segments)

    missing = [segment for segment in target_segments if segment.index not in recovered]

    for attempt in range(1, 3):
        if not missing:
            break
        if progress_callback:
            progress_callback(
                max(0.02, min(0.91, (chunk_number - 0.2) / max(1, total_chunks) * 0.82 + 0.02)),
                f"Recovering {len(missing)} missing subtitle{'s' if len(missing) != 1 else ''} together · attempt {attempt}/2",
            )
        recovery_prompt = build_missing_recovery_prompt(
            prompt,
            target_segments,
            missing,
            recovered,
            target_label,
            last_output,
        )
        missing_text = "\n".join(segment.text for segment in missing)
        recovery_output = runtime.generate(
            recovery_prompt,
            max_output_tokens=max(256, min(max_output_tokens, estimate_tokens(missing_text) * 3 + 256)),
        )
        last_output = recovery_output
        absorb(recovery_output, missing)
        missing = [segment for segment in target_segments if segment.index not in recovered]

    if len(missing) == 1:
        segment = missing[0]
        try:
            candidate = clean_single_line_output(last_output, segment.index)
            recovered[segment.index] = validate_translation_text(
                candidate,
                target_language=target_language,
                segment_id=segment.index,
            )
            missing = []
        except DubLocalError:
            if progress_callback:
                progress_callback(
                    max(0.02, min(0.92, (chunk_number - 0.1) / max(1, total_chunks) * 0.83 + 0.02)),
                    f"Final compact recovery for subtitle {segment.index}",
                )
            single_raw = runtime.generate(
                build_single_line_recovery_prompt(prompt, segment, target_label, last_output),
                max_output_tokens=max(128, min(384, estimate_tokens(segment.text) * 4 + 96)),
            )
            partial = recover_partial_output(single_raw, [segment])
            candidate = (
                partial[segment.index]
                if segment.index in partial
                else clean_single_line_output(single_raw, segment.index)
            )
            recovered[segment.index] = validate_translation_text(
                candidate,
                target_language=target_language,
                segment_id=segment.index,
            )
            missing = []

    if missing:
        still_missing = [segment.index for segment in missing]
        raise DubLocalError(
            "Contextual translator could not recover all required subtitle IDs "
            f"for batch {chunk_number}/{total_chunks} after bounded batch recovery "
            f"(missing={still_missing[:8]}). DubLocal stopped instead of writing a corrupted SRT."
        )

    expected = [segment.index for segment in target_segments]
    return [recovered[index] for index in expected]


def _review_chunk(
    runtime: ContextualRuntime,
    original_prompt: str,
    target_segments: Sequence[Segment],
    draft_texts: Sequence[str],
    target_language: str,
    *,
    max_output_tokens: int,
    chunk_number: int,
    total_chunks: int,
    progress_callback: ProgressCallback | None,
) -> list[str]:
    if progress_callback:
        progress_callback(
            min(0.96, 0.55 + (chunk_number - 1) / max(1, total_chunks) * 0.38),
            f"Reviewing translation quality {chunk_number}/{total_chunks}",
        )
    review_prompt = build_review_prompt(
        original_prompt,
        target_segments,
        draft_texts,
        target_language,
    )
    try:
        raw = runtime.generate(review_prompt, max_output_tokens=max_output_tokens)
        reviewed = recover_chunk_output(raw, target_segments)
        return _validated_chunk(reviewed, target_segments, target_language)
    except DubLocalError:
        return list(draft_texts)


def translate_srt_contextual_with_progress(
    subtitle_path: str | Path,
    source_language: str,
    target_language: str,
    *,
    review: bool | None = None,
    model_key: str | None = None,
    context_cap_tokens: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TranslationResult:
    """Adaptive contextual translation using the recommended local model/profile for this Mac."""

    recommendation = active_recommendation()
    selected_model_key = model_key or recommendation.model_key
    selected_review = recommendation.review if review is None else bool(review)
    requested_context_cap = (
        recommendation.context_cap_tokens
        if context_cap_tokens is None
        else max(4096, int(context_cap_tokens))
    )
    spec = contextual_model_spec(selected_model_key)

    path = Path(subtitle_path).expanduser().resolve()
    if not path.is_file():
        raise DubLocalError("The subtitle file is no longer available. Extract or transcribe it again.")
    if path.suffix.lower() != ".srt":
        raise DubLocalError("Contextual translation expects DubLocal's normalized SRT timeline.")

    requested_source = normalise_language_code(source_language)
    source = requested_source
    source_is_auto = source == "auto"
    target = normalise_language_code(target_language)
    if not source_is_auto and source not in TRANSLATION_LANGUAGES:
        raise DubLocalError("Choose a supported subtitle source language.")
    if target not in TRANSLATION_LANGUAGES:
        raise DubLocalError("Choose a supported translation target language.")
    if not source_is_auto and source == target:
        raise DubLocalError("Source and target languages are the same; no translation is needed.")

    try:
        source_srt_text = path.read_text(encoding="utf-8", errors="replace")
        segments = parse_srt(source_srt_text)
    except ValueError as exc:
        raise DubLocalError(f"Could not read the subtitle timeline: {exc}") from exc
    if not segments:
        raise DubLocalError("The subtitle file contains no timed text to translate.")

    selected_context_cap = effective_context_cap(segments, requested_context_cap)
    plan = context_plan(segments)
    if plan.input_budget_tokens > selected_context_cap:
        plan = replace(plan, input_budget_tokens=selected_context_cap)
    runtime_context_tokens = min(
        int(spec.metadata["native_context"]),
        selected_context_cap + 4096,
    )

    adaptive_max_batch = adaptive_batch_max(selected_model_key, segments)
    batch_state = _AdaptiveBatchState(
        current=adaptive_max_batch,
        maximum=adaptive_max_batch,
    )

    cache_key = translation_cache_key(
        source_srt_text,
        requested_source_language=requested_source,
        target_language=target,
        model_key=selected_model_key,
        model_revision=str(spec.metadata.get("revision") or ""),
        model_sha256=str(spec.metadata.get("sha256") or ""),
        review=selected_review,
        context_cap_tokens=selected_context_cap,
        chunk_segments=adaptive_max_batch,
        input_budget_tokens=plan.input_budget_tokens,
        prompt_version=f"{CONTEXTUAL_PROMPT_VERSION}+{_ADAPTIVE_CACHE_POLICY}",
    )
    cached = _validated_cached_translation(
        load_translation_cache(cache_key, segments, target_language=target),
        segments,
        target,
    )
    if cached is not None:
        if progress_callback:
            progress_callback(0.05, "Reusing verified local translation cache")
        output = _write_translation_output(cached.segments, target)
        if progress_callback:
            progress_callback(1.0, "Contextual translation ready from local cache")
        route = cached.route
        if "cache hit" not in route.casefold():
            route += " · cache hit"
        return TranslationResult(
            srt_path=output,
            segments=cached.segments,
            source_language=cached.source_language,
            target_language=target,
            route=route,
        )

    if not _llama_command() or not contextual_model_valid(selected_model_key):
        raise ContextualTranslationMissingError(
            f"{spec.label} contextual translation is not prepared. Open Settings → Model Manager → Contextual translation and click Prepare / verify."
        )

    translated: list[TranslatedSegment] = []
    protected_count = sum(1 for segment in segments if is_protected_caption_tag(segment.text))
    needs_model = protected_count < len(segments) or source_is_auto
    runtime_mode = "not needed"
    initial_batches = max(1, (len(segments) + adaptive_max_batch - 1) // adaptive_max_batch)

    if progress_callback:
        progress_callback(
            0.02,
            f"Preparing adaptive translation · up to {adaptive_max_batch} subtitles per batch · {protected_count} protected tag(s)",
        )

    runtime: ContextualRuntime | None = None
    committed_batch_sizes: list[int] = []
    completed_batches = 0
    try:
        if needs_model:
            if progress_callback:
                pass_name = " + review" if selected_review else ""
                progress_callback(
                    0.03,
                    f"Loading {spec.label}{pass_name} once for this translation · about {initial_batches} fast batch(es) if alignment stays clean",
                )
            runtime = ContextualRuntime(
                model_key=selected_model_key,
                context_tokens=runtime_context_tokens,
            ).__enter__()
            runtime_mode = runtime.mode

        if source_is_auto:
            assert runtime is not None
            if progress_callback:
                progress_callback(0.04, "Auto-detecting subtitle source language")
            source = _detect_source_language(runtime, segments)
            if source == target:
                raise DubLocalError(
                    f"Auto detected {TRANSLATION_LANGUAGES[source]['label']}, which is already the target language; no translation is needed."
                )
            if progress_callback:
                progress_callback(
                    0.05,
                    f"Detected {TRANSLATION_LANGUAGES[source]['label']} · starting translation",
                )

        start = 0
        while start < len(segments):
            attempt_span = min(batch_state.current, len(segments) - start)
            end = start + attempt_span
            target_segments = segments[start:end]
            model_targets = [
                segment for segment in target_segments if not is_protected_caption_tag(segment.text)
            ]
            translated_map: dict[int, str] = {}
            used_recovery = False
            batch_number = completed_batches + 1
            estimated_total = completed_batches + max(
                1,
                (len(segments) - start + batch_state.current - 1) // batch_state.current,
            )

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

                primary_raw = runtime.generate(prompt, max_output_tokens=max_output_tokens)
                try:
                    draft = _validated_chunk(
                        recover_chunk_output(primary_raw, model_targets),
                        model_targets,
                        target,
                    )
                except DubLocalError:
                    if len(model_targets) > batch_state.minimum and batch_state.shrink(attempt_span):
                        if progress_callback:
                            progress_callback(
                                min(0.94, start / max(1, len(segments)) * 0.90 + 0.04),
                                f"Large batch did not align cleanly · retrying this section as {batch_state.current} subtitles instead of {attempt_span}",
                            )
                        continue

                    used_recovery = True
                    draft = _translate_chunk_with_recovery(
                        runtime,
                        prompt,
                        model_targets,
                        target,
                        max_output_tokens=max_output_tokens,
                        chunk_number=batch_number,
                        total_chunks=estimated_total,
                        progress_callback=progress_callback,
                        initial_raw=primary_raw,
                    )

                chunk = (
                    _review_chunk(
                        runtime,
                        prompt,
                        model_targets,
                        draft,
                        target,
                        max_output_tokens=max_output_tokens,
                        chunk_number=batch_number,
                        total_chunks=estimated_total,
                        progress_callback=progress_callback,
                    )
                    if selected_review
                    else draft
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

            committed_batch_sizes.append(attempt_span)
            start = end
            completed_batches += 1
            batch_state.mark_success(recovered=used_recovery)

            if progress_callback:
                status = (
                    f"Translated + reviewed {start}/{len(segments)} subtitles"
                    if selected_review
                    else f"Translated {start}/{len(segments)} subtitles"
                )
                progress_callback(
                    min(0.97, start / max(1, len(segments)) * 0.92 + 0.04),
                    f"{status} · next batch up to {batch_state.current}",
                )
    finally:
        if runtime is not None:
            runtime.__exit__(None, None, None)

    output = _write_translation_output(translated, target)
    if progress_callback:
        progress_callback(1.0, "Contextual translation complete")

    active_sizes = [size for size in committed_batch_sizes if size > 0]
    if active_sizes:
        smallest_batch = min(active_sizes)
        largest_batch = max(active_sizes)
        batch_route = (
            f"adaptive batches {smallest_batch}–{largest_batch}"
            if smallest_batch != largest_batch
            else f"adaptive batches {largest_batch}"
        )
    else:
        batch_route = "adaptive batches not needed"
    if batch_state.split_count:
        batch_route += f" · {batch_state.split_count} safe split{'s' if batch_state.split_count != 1 else ''}"

    route = (
        f"{spec.label} {'+ review' if selected_review else 'single pass'} · "
        f"{TRANSLATION_LANGUAGES[source]['label']} → {TRANSLATION_LANGUAGES[target]['label']} · "
        f"{plan.input_budget_tokens}-token input · {batch_route} · {runtime_mode}"
    )
    save_translation_cache(
        cache_key,
        translated,
        source_language=source,
        target_language=target,
        route=route,
    )
    return TranslationResult(
        srt_path=output,
        segments=translated,
        source_language=source,
        target_language=target,
        route=route,
    )
