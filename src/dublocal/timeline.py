from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_TIMESTAMP_RE = re.compile(
    r"^(?P<hours>\d{1,3}):(?P<minutes>\d{2}):(?P<seconds>\d{2})[,.](?P<millis>\d{3})$"
)


@dataclass(frozen=True, slots=True)
class Segment:
    """One normalized subtitle/transcription segment using integer millisecond timing."""

    index: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


def parse_timestamp(value: str) -> int:
    match = _TIMESTAMP_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle timestamp: {value!r}")

    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis = int(match.group("millis"))
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis


def format_timestamp(milliseconds: int) -> str:
    value = max(0, int(milliseconds))
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_srt(text: str) -> list[Segment]:
    """Parse standard SRT into DubLocal's normalized segment representation."""

    normalized = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    segments: list[Segment] = []
    blocks = re.split(r"\n\s*\n", normalized)

    for block in blocks:
        lines = [line.rstrip() for line in block.split("\n")]
        if not lines:
            continue

        cursor = 0
        index = len(segments) + 1
        if lines[0].strip().isdigit():
            index = int(lines[0].strip())
            cursor = 1

        if cursor >= len(lines) or "-->" not in lines[cursor]:
            continue

        start_raw, end_raw = [part.strip() for part in lines[cursor].split("-->", 1)]
        # SRT may append cue settings after the end timestamp. Whisper does not, but
        # accepting them keeps the parser useful for imported captions too.
        end_raw = end_raw.split()[0]
        start_ms = parse_timestamp(start_raw)
        end_ms = parse_timestamp(end_raw)
        if end_ms < start_ms:
            raise ValueError(f"Subtitle segment {index} ends before it starts")

        body = "\n".join(lines[cursor + 1 :]).strip()
        if not body:
            continue

        segments.append(
            Segment(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=body,
            )
        )

    return segments


def segments_to_srt(segments: Iterable[Segment]) -> str:
    """Serialize normalized segments to standard UTF-8 SRT text."""

    blocks: list[str] = []
    for fallback_index, segment in enumerate(segments, start=1):
        index = segment.index if segment.index > 0 else fallback_index
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_timestamp(segment.start_ms)} --> {format_timestamp(segment.end_ms)}",
                    segment.text.strip(),
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def segments_to_rows(segments: Iterable[Segment]) -> list[list[str]]:
    return [
        [format_timestamp(segment.start_ms), format_timestamp(segment.end_ms), segment.text]
        for segment in segments
    ]
