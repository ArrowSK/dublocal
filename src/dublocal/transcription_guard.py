from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from . import transcription
from .media import DubLocalError
from .timeline import Segment, parse_srt, segments_to_srt


# Accurate/Large-v3-Turbo is the UI profile for songs and difficult audio.
# Singing does not pair reliably with speech VAD, so this profile uses Whisper's
# decoder directly but disables rolling text context to prevent self-reinforcing
# long-form repetition loops.
_SINGING_FRIENDLY_MODEL = "large-v3-turbo-q5_0"

_ORIGINAL_RUN = transcription._run_whisper_with_progress
_ORIGINAL_TRANSCRIBE = transcription.transcribe_source
_INSTALLED = False

_VAD_VALUE_OPTIONS = {
    "--vad-model",
    "--vad-threshold",
    "--vad-min-speech-duration-ms",
    "--vad-min-silence-duration-ms",
    "--vad-max-speech-duration-s",
    "--vad-speech-pad-ms",
    "--vad-samples-overlap",
}
_OPTION_ALIASES = {
    "-mc": "--max-context",
    "--max-context": "-mc",
    "-et": "--entropy-thold",
    "--entropy-thold": "-et",
    "-ot": "--offset-t",
    "--offset-t": "-ot",
    "-d": "--duration",
    "--duration": "-d",
    "-of": "--output-file",
    "--output-file": "-of",
}
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_QUALITY_NOTES: dict[str, str] = {}


@dataclass(frozen=True, slots=True)
class _RepeatRun:
    start_pos: int
    end_pos: int
    start_ms: int
    end_ms: int
    count: int

    @property
    def span_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    @property
    def severe(self) -> bool:
        return self.count >= 10 or self.span_ms >= 45_000


def quality_note_for(path: str | Path) -> str:
    try:
        key = str(Path(path).resolve())
    except OSError:
        key = str(Path(path))
    return _QUALITY_NOTES.get(key, "")


def _remember_quality_note(path: Path, note: str) -> None:
    try:
        key = str(path.resolve())
    except OSError:
        key = str(path)
    if note:
        _QUALITY_NOTES[key] = note
    else:
        _QUALITY_NOTES.pop(key, None)


def _without_vad(command: list[str]) -> list[str]:
    output: list[str] = []
    index = 0
    while index < len(command):
        item = command[index]
        if item == "--vad":
            index += 1
            continue
        if item in _VAD_VALUE_OPTIONS:
            index += 2
            continue
        output.append(item)
        index += 1
    return output


def _option_index(command: list[str], option: str) -> int | None:
    aliases = {option, _OPTION_ALIASES.get(option, "")}
    for index, item in enumerate(command):
        if item in aliases:
            return index
    return None


def _set_option(command: list[str], option: str, value: str) -> list[str]:
    output = list(command)
    index = _option_index(output, option)
    if index is None:
        output.extend([option, value])
    elif index + 1 < len(output):
        output[index + 1] = value
    else:
        output.append(value)
    return output


def _output_prefix(command: list[str]) -> Path | None:
    index = _option_index(command, "-of")
    if index is None or index + 1 >= len(command):
        return None
    return Path(command[index + 1])


def _model_path(command: list[str]) -> str:
    try:
        return str(command[command.index("-m") + 1])
    except (ValueError, IndexError):
        try:
            return str(command[command.index("--model") + 1])
        except (ValueError, IndexError):
            return ""


def _is_accurate_music_command(command: list[str]) -> bool:
    return _SINGING_FRIENDLY_MODEL in Path(_model_path(command)).name


def _prepare_command(command: list[str]) -> list[str]:
    output = list(command)
    if _is_accurate_music_command(output):
        # whisper.cpp conditions long-form decoding on previous text whenever max
        # context is > 0. Setting it to 0 prevents one bad lyric from becoming the
        # prompt that drives the next minute of audio.
        output = _set_option(output, "-mc", "0")
        # A slightly higher entropy threshold is a conservative anti-repetition
        # setting recommended in upstream whisper.cpp hallucination discussions.
        output = _set_option(output, "-et", "2.60")
    return output


def _clear_partial_outputs(command: list[str]) -> None:
    prefix = _output_prefix(command)
    if prefix is None:
        return
    for suffix in (".srt", ".json"):
        prefix.with_suffix(suffix).unlink(missing_ok=True)


def _srt_ready(command: list[str]) -> bool:
    prefix = _output_prefix(command)
    if prefix is None:
        return False
    path = prefix.with_suffix(".srt")
    return path.is_file() and path.stat().st_size > 0


def _words(text: str) -> list[str]:
    return [token.casefold() for token in _WORD_RE.findall(text)]


def _text_similarity(left: str, right: str) -> float:
    a = _words(left)
    b = _words(right)
    if not a or not b:
        return 0.0

    joined_a = " ".join(a)
    joined_b = " ".join(b)
    sequence = SequenceMatcher(None, joined_a, joined_b).ratio()

    if len(a) == 1 or len(b) == 1:
        containment = 1.0 if a == b else 0.0
    else:
        a_pairs = set(zip(a, a[1:]))
        b_pairs = set(zip(b, b[1:]))
        shorter = min(len(a_pairs), len(b_pairs))
        containment = len(a_pairs & b_pairs) / shorter if shorter else 0.0

    return max(sequence, containment)


def _find_repeat_runs(segments: list[Segment]) -> list[_RepeatRun]:
    """Find pathological consecutive near-duplicate subtitle storms.

    The thresholds are intentionally conservative. Legitimate repeated choruses of
    two or three lines are left alone; the guard targets the long, low-diversity
    loops typical of Whisper ghosting.
    """

    runs: list[_RepeatRun] = []
    start = 0
    while start < len(segments):
        end = start
        while end + 1 < len(segments):
            candidate = segments[end + 1]
            recent = segments[max(start, end - 2) : end + 1]
            if max(_text_similarity(candidate.text, item.text) for item in recent) < 0.84:
                break
            end += 1

        count = end - start + 1
        span_ms = segments[end].end_ms - segments[start].start_ms
        if count >= 5 and span_ms >= 12_000:
            runs.append(
                _RepeatRun(
                    start_pos=start,
                    end_pos=end,
                    start_ms=segments[start].start_ms,
                    end_ms=segments[end].end_ms,
                    count=count,
                )
            )
        start = end + 1
    return runs


def _parse_srt_file(path: Path) -> list[Segment]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    try:
        return parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []


def _reindex(segments: list[Segment]) -> list[Segment]:
    return [
        Segment(
            index=index,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
        )
        for index, segment in enumerate(segments, start=1)
    ]


def _recovery_command(
    command: list[str],
    *,
    run: _RepeatRun,
    ordinal: int,
) -> tuple[list[str], Path, int, int]:
    prefix = _output_prefix(command)
    if prefix is None:
        raise DubLocalError("Whisper hallucination recovery could not resolve the output path.")

    start_ms = max(0, run.start_ms - 1_500)
    end_ms = run.end_ms + 1_500
    duration_ms = max(1_000, end_ms - start_ms)

    recovery_prefix = prefix.parent / f"{prefix.name}.recovery-{ordinal}"
    output = _without_vad(command)
    output = _set_option(output, "-mc", "0")
    output = _set_option(output, "-et", "2.60")
    output = _set_option(output, "-ot", str(start_ms))
    output = _set_option(output, "-d", str(duration_ms))
    output = _set_option(output, "-of", str(recovery_prefix))
    _clear_partial_outputs(output)
    return output, recovery_prefix, start_ms, duration_ms


def _normalise_recovery_timestamps(
    segments: list[Segment],
    *,
    offset_ms: int,
    duration_ms: int,
) -> list[Segment]:
    if not segments or offset_ms <= 0:
        return segments

    # whisper.cpp normally reports absolute timestamps for --offset-t. Some builds
    # have emitted range-relative timestamps, so normalize that variant defensively.
    latest = max(segment.end_ms for segment in segments)
    earliest = min(segment.start_ms for segment in segments)
    if earliest < max(2_000, offset_ms // 4) and latest <= duration_ms + 3_000:
        return [
            Segment(
                index=segment.index,
                start_ms=segment.start_ms + offset_ms,
                end_ms=segment.end_ms + offset_ms,
                text=segment.text,
            )
            for segment in segments
        ]
    return segments


def _recover_repeat_run(
    command: list[str],
    run: _RepeatRun,
    ordinal: int,
) -> tuple[list[Segment] | None, str]:
    recovery_command, recovery_prefix, offset_ms, duration_ms = _recovery_command(
        command,
        run=run,
        ordinal=ordinal,
    )
    try:
        _ORIGINAL_RUN(recovery_command)
    except DubLocalError:
        return None, "retry failed"

    recovered = _parse_srt_file(recovery_prefix.with_suffix(".srt"))
    recovered = _normalise_recovery_timestamps(
        recovered,
        offset_ms=offset_ms,
        duration_ms=duration_ms,
    )
    recovered = [
        segment
        for segment in recovered
        if segment.end_ms > run.start_ms and segment.start_ms < run.end_ms
    ]

    if not recovered:
        return [], "isolated retry found no reliable speech"

    if _find_repeat_runs(recovered):
        return None, "isolated retry repeated the same pattern"

    return recovered, "isolated retry recovered the range"


def _repair_repetition(command: list[str]) -> None:
    prefix = _output_prefix(command)
    if prefix is None:
        return
    srt_path = prefix.with_suffix(".srt")
    segments = _parse_srt_file(srt_path)
    runs = _find_repeat_runs(segments)
    if not segments or not runs:
        _remember_quality_note(srt_path, "")
        return

    # Keep the raw decoder output in the temporary job cache for diagnostics. The
    # cleaned SRT remains the file that reaches translation/TTS.
    raw_path = prefix.parent / f"{prefix.name}.raw.srt"
    try:
        raw_path.write_text(segments_to_srt(segments), encoding="utf-8")
    except OSError:
        pass

    replacements: dict[int, tuple[int, list[Segment]]] = {}
    recovered_count = 0
    suppressed_count = 0
    suppressed_segments = 0
    unresolved_count = 0

    for ordinal, run in enumerate(runs, start=1):
        replacement, _reason = _recover_repeat_run(command, run, ordinal)
        if replacement is not None:
            replacements[run.start_pos] = (run.end_pos, replacement)
            if replacement:
                recovered_count += 1
            else:
                suppressed_count += 1
                suppressed_segments += run.count
            continue

        # If a long repetition storm survives an independent no-context retry,
        # passing it downstream is more harmful than leaving a subtitle gap.
        # The same applies to an intro loop before 30 s. Shorter ambiguous repeated
        # phrases are preserved rather than risking removal of a legitimate chorus.
        if run.severe or (run.start_ms < 30_000 and run.count >= 5):
            replacements[run.start_pos] = (run.end_pos, [])
            suppressed_count += 1
            suppressed_segments += run.count
        else:
            unresolved_count += 1

    if replacements:
        cleaned: list[Segment] = []
        position = 0
        while position < len(segments):
            replacement = replacements.get(position)
            if replacement is None:
                cleaned.append(segments[position])
                position += 1
                continue
            end_pos, replacement_segments = replacement
            cleaned.extend(replacement_segments)
            position = end_pos + 1

        cleaned.sort(key=lambda item: (item.start_ms, item.end_ms))
        cleaned = _reindex(cleaned)
        srt_path.write_text(segments_to_srt(cleaned), encoding="utf-8")

    parts = []
    if recovered_count:
        parts.append(f"recovered {recovered_count} suspicious region(s)")
    if suppressed_count:
        parts.append(
            f"suppressed {suppressed_segments} repeated segment(s) "
            f"across {suppressed_count} untrusted region(s)"
        )
    if unresolved_count:
        parts.append(f"left {unresolved_count} short ambiguous repetition(s) unchanged")
    if parts:
        _remember_quality_note(
            srt_path,
            "Anti-hallucination guard: " + "; ".join(parts) + ".",
        )


def _run_with_vad_fallback(command: list[str]) -> None:
    """Run one Whisper job with fail-safe VAD and repetition protection."""

    prepared = _prepare_command(command)

    if "--vad" not in prepared:
        _ORIGINAL_RUN(prepared)
        if _srt_ready(prepared):
            _repair_repetition(prepared)
        return

    fallback = _without_vad(prepared)
    try:
        _ORIGINAL_RUN(prepared)
    except DubLocalError:
        _clear_partial_outputs(prepared)
        _ORIGINAL_RUN(fallback)
        if _srt_ready(fallback):
            _repair_repetition(fallback)
        return

    if not _srt_ready(prepared):
        _clear_partial_outputs(prepared)
        _ORIGINAL_RUN(fallback)
        prepared = fallback

    if _srt_ready(prepared):
        _repair_repetition(prepared)


def _transcribe_with_media_policy(
    info: dict[str, Any],
    model_id: str = "base",
    language: str = "auto",
):
    if model_id != _SINGING_FRIENDLY_MODEL:
        return _ORIGINAL_TRANSCRIBE(info, model_id=model_id, language=language)

    # Accurate/Large-v3-Turbo is the UI's song/music-video recommendation. Silero VAD
    # can classify singing as non-speech, so do not gate this profile through VAD.
    # _prepare_command() simultaneously turns off rolling text context for this model.
    original_support = transcription._whisper_supports_vad
    transcription._whisper_supports_vad = lambda _executable: False
    try:
        return _ORIGINAL_TRANSCRIBE(info, model_id=model_id, language=language)
    finally:
        transcription._whisper_supports_vad = original_support


def install_transcription_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    transcription._run_whisper_with_progress = _run_with_vad_fallback
    transcription.transcribe_source = _transcribe_with_media_policy
    _INSTALLED = True
