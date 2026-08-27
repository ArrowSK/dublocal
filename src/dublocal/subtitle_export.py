from __future__ import annotations

from pathlib import Path

from .media import DubLocalError
from .timeline import Segment, parse_srt


SUBTITLE_FORMAT_CHOICES = [
    ("SRT · SubRip · recommended", "srt"),
    ("VTT · WebVTT", "vtt"),
    ("TXT · plain text", "txt"),
]


def _vtt_timestamp(ms: int) -> str:
    total_ms = max(0, int(ms))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _segments(path: Path) -> list[Segment]:
    try:
        return parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        raise DubLocalError(f"Could not read the generated subtitle timeline: {exc}") from exc


def export_subtitle(srt_path: str | Path, output_format: str = "srt") -> Path:
    """Create a user-facing subtitle file while keeping SRT as DubLocal's internal timeline."""

    source = Path(srt_path).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("The generated subtitle timeline is no longer available.")
    if source.suffix.lower() != ".srt":
        raise DubLocalError("DubLocal can export only from its normalized SRT timeline.")

    format_id = (output_format or "srt").strip().lower()
    if format_id == "srt":
        return source
    if format_id not in {"vtt", "txt"}:
        raise DubLocalError(f"Unsupported subtitle download format: {output_format}")

    segments = _segments(source)
    if not segments:
        raise DubLocalError("The generated subtitle timeline contains no timed text.")

    destination = source.with_suffix(f".{format_id}")
    if format_id == "vtt":
        blocks = ["WEBVTT", ""]
        for segment in segments:
            blocks.extend(
                [
                    str(segment.index),
                    f"{_vtt_timestamp(segment.start_ms)} --> {_vtt_timestamp(segment.end_ms)}",
                    segment.text,
                    "",
                ]
            )
        destination.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    else:
        destination.write_text(
            "\n".join(segment.text for segment in segments).rstrip() + "\n",
            encoding="utf-8",
        )

    return destination
