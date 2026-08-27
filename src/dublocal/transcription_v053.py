from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path

from . import transcription
from . import transcription_guard as guard
from .hardware_profile import detect_hardware_profile
from .timeline import Segment, parse_srt, segments_to_srt


_ACCURATE_MODEL = "large-v3-turbo-q5_0"
_INSTALLED = False
_ORIGINAL_TRANSCRIBE = transcription.transcribe_source


@dataclass(frozen=True, slots=True)
class _RecoveryRegion:
    kind: str
    start_ms: int
    end_ms: int
    segment_index: int | None = None
    original_text: str = ""
    left_text: str = ""
    right_text: str = ""

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


def _words(text: str) -> list[str]:
    return guard._words(text)


def _similarity(left: str, right: str) -> float:
    return guard._text_similarity(left, right)


def _is_caption_cue(text: str) -> bool:
    value = text.strip()
    return len(value) >= 2 and value.startswith("[") and value.endswith("]")


def _recovery_budget() -> tuple[int, int]:
    """Return (max regions, max total milliseconds) with an M1-safe ceiling."""

    hardware = detect_hardware_profile()
    memory = hardware.memory_gib
    if hardware.intel_mac:
        return 2, 18_000
    if hardware.apple_silicon and memory is not None and memory < 12:
        # 8 GB M1-class Macs: only a few short isolated verification passes.
        return 3, 24_000
    if hardware.apple_silicon:
        return 5, 40_000
    return 3, 24_000


def _candidate_regions(segments: list[Segment], model_id: str) -> list[_RecoveryRegion]:
    candidates: list[_RecoveryRegion] = []

    # Existing low-density long segments can indicate that Whisper heard the line but
    # dropped words. They are safer recovery candidates than blind silence probing.
    for segment in segments:
        if _is_caption_cue(segment.text):
            continue
        duration = segment.end_ms - segment.start_ms
        word_count = len(_words(segment.text))
        if duration >= 3_500 and 1 <= word_count <= 3:
            candidates.append(
                _RecoveryRegion(
                    kind="sparse",
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    segment_index=segment.index,
                    original_text=segment.text,
                )
            )

    # Music/singing is intentionally not VAD-gated in the Accurate profile. Recover
    # only short INTERNAL holes bounded by real text, never intros/outros or long rests.
    if model_id == _ACCURATE_MODEL:
        for left, right in zip(segments, segments[1:]):
            gap = right.start_ms - left.end_ms
            if not 1_400 <= gap <= 4_500:
                continue
            if len(_words(left.text)) < 2 or len(_words(right.text)) < 2:
                continue
            candidates.append(
                _RecoveryRegion(
                    kind="gap",
                    start_ms=left.end_ms,
                    end_ms=right.start_ms,
                    left_text=left.text,
                    right_text=right.text,
                )
            )

    # Prefer sparse known-speech ranges, then shorter gaps. Avoid overlapping retries.
    candidates.sort(key=lambda item: (0 if item.kind == "sparse" else 1, item.duration_ms))
    selected: list[_RecoveryRegion] = []
    for candidate in candidates:
        if any(
            candidate.start_ms < existing.end_ms and candidate.end_ms > existing.start_ms
            for existing in selected
        ):
            continue
        selected.append(candidate)
    return selected


def _isolated_command(
    result: transcription.TranscriptionResult,
    wav: Path,
    region: _RecoveryRegion,
    prefix: Path,
    *,
    conservative: bool,
) -> list[str]:
    executable = transcription.find_whisper_cli()
    if not executable:
        return []
    model = transcription.whisper_model_path(result.model_id)
    if not model.is_file():
        return []

    start_ms = max(0, region.start_ms - 300)
    end_ms = region.end_ms + 300
    language = (result.language or "auto").strip().lower()
    command = [
        executable,
        "-m",
        str(model),
        "-f",
        str(wav),
        "-osrt",
        "-of",
        str(prefix),
        "-l",
        language,
        "-mc",
        "0",
        "-ot",
        str(start_ms),
        "-d",
        str(max(1_000, end_ms - start_ms)),
        "-et",
        "2.40" if not conservative else "2.20",
        "-nth",
        "0.60",
    ]
    if conservative:
        command += ["-lpt", "-0.85", "-nf"]
    if platform.machine().lower() in {"x86_64", "amd64"}:
        command.append("-ng")
    return command


def _run_isolated(
    result: transcription.TranscriptionResult,
    wav: Path,
    region: _RecoveryRegion,
    prefix: Path,
    *,
    conservative: bool,
) -> list[Segment]:
    command = _isolated_command(result, wav, region, prefix, conservative=conservative)
    if not command:
        return []
    guard._clear_partial_outputs(command)
    try:
        guard._ORIGINAL_RUN(command)
    except Exception:
        return []

    segments = guard._parse_srt_file(prefix.with_suffix(".srt"))
    if not segments:
        return []
    offset_index = guard._option_index(command, "-ot")
    duration_index = guard._option_index(command, "-d")
    offset_ms = int(command[offset_index + 1]) if offset_index is not None else 0
    duration_ms = int(command[duration_index + 1]) if duration_index is not None else 0
    segments = guard._normalise_recovery_timestamps(
        segments,
        offset_ms=offset_ms,
        duration_ms=duration_ms,
    )
    if guard._find_repeat_runs(segments):
        return []
    return segments


def _combined_text(segments: list[Segment]) -> str:
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()


def _verified_recovery(
    result: transcription.TranscriptionResult,
    wav: Path,
    region: _RecoveryRegion,
    ordinal: int,
) -> list[Segment] | None:
    root = result.srt_path.parent
    first = _run_isolated(
        result,
        wav,
        region,
        root / f"smart-recovery-{ordinal}-a",
        conservative=False,
    )
    second = _run_isolated(
        result,
        wav,
        region,
        root / f"smart-recovery-{ordinal}-b",
        conservative=True,
    )
    if not first or not second:
        return None

    text_a = _combined_text(first)
    text_b = _combined_text(second)
    if not text_a or not text_b or _similarity(text_a, text_b) < 0.80:
        return None

    chosen = first if len(_words(text_a)) >= len(_words(text_b)) else second
    chosen_text = _combined_text(chosen)
    if len(_words(chosen_text)) < 2:
        return None

    if region.kind == "gap":
        # Reject the common ghost failure mode where an isolated retry simply echoes
        # the neighbouring lyric/dialogue into a quiet gap.
        if max(_similarity(chosen_text, region.left_text), _similarity(chosen_text, region.right_text)) >= 0.78:
            return None
        accepted: list[Segment] = []
        for segment in chosen:
            midpoint = (segment.start_ms + segment.end_ms) // 2
            if not region.start_ms <= midpoint <= region.end_ms:
                continue
            start = max(region.start_ms, segment.start_ms)
            end = min(region.end_ms, segment.end_ms)
            if end - start < 300:
                continue
            accepted.append(Segment(segment.index, start, end, segment.text))
        return accepted or None

    # For a sparse existing line, only accept a richer consensus transcription that
    # still resembles the original. This prevents replacement with a plausible but
    # unrelated hallucination. Preserve the original subtitle time window exactly.
    original_words = len(_words(region.original_text))
    if len(_words(chosen_text)) < original_words + 2:
        return None
    if _similarity(chosen_text, region.original_text) < 0.32:
        return None
    return [
        Segment(
            index=region.segment_index or 0,
            start_ms=region.start_ms,
            end_ms=region.end_ms,
            text=chosen_text,
        )
    ]


def _apply_recoveries(
    segments: list[Segment],
    accepted: list[tuple[_RecoveryRegion, list[Segment]]],
) -> list[Segment]:
    sparse: dict[int, Segment] = {}
    additions: list[Segment] = []
    for region, recovered in accepted:
        if region.kind == "sparse" and region.segment_index is not None and recovered:
            sparse[region.segment_index] = recovered[0]
        elif region.kind == "gap":
            additions.extend(recovered)

    merged: list[Segment] = []
    for segment in segments:
        replacement = sparse.get(segment.index)
        merged.append(replacement if replacement is not None else segment)
    merged.extend(additions)
    merged.sort(key=lambda item: (item.start_ms, item.end_ms, item.index))
    return guard._reindex(merged)


def _transcribe_with_smart_recovery(
    info: dict,
    model_id: str = "base",
    language: str = "auto",
):
    result = _ORIGINAL_TRANSCRIBE(info, model_id=model_id, language=language)
    srt_path = Path(result.srt_path)
    wav = srt_path.parent / "speech-16k-mono.wav"
    if not srt_path.is_file() or not wav.is_file():
        return result

    try:
        segments = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return result
    if len(segments) < 2:
        return result

    max_regions, max_total_ms = _recovery_budget()
    candidates = _candidate_regions(segments, model_id)
    accepted: list[tuple[_RecoveryRegion, list[Segment]]] = []
    attempted = 0
    used_ms = 0

    for region in candidates:
        if attempted >= max_regions or used_ms + region.duration_ms > max_total_ms:
            break
        attempted += 1
        used_ms += region.duration_ms
        recovered = _verified_recovery(result, wav, region, attempted)
        if recovered:
            accepted.append((region, recovered))

    if not accepted:
        return result

    cleaned = _apply_recoveries(segments, accepted)
    try:
        srt_path.write_text(segments_to_srt(cleaned), encoding="utf-8")
    except OSError:
        return result

    existing = guard.quality_note_for(srt_path)
    addition = (
        f"Smart recovery: restored {len(accepted)} low-confidence/missing region(s) "
        f"after two isolated passes agreed; checked {attempted} region(s)."
    )
    guard._remember_quality_note(srt_path, f"{existing} {addition}".strip())
    return transcription.TranscriptionResult(
        srt_path=srt_path,
        segments=cleaned,
        model_id=result.model_id,
        language=result.language,
        vad_used=result.vad_used,
    )


def install_transcription_refinements() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    transcription.transcribe_source = _transcribe_with_smart_recovery
    _INSTALLED = True
