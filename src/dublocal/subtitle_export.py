from __future__ import annotations

import csv
import io
from pathlib import Path

from .contextual_translation import _new_job_dir
from .media import DubLocalError
from .timeline import Segment, format_timestamp, parse_srt, segments_to_srt


SUBTITLE_EXPORT_CHOICES = [
    ("SRT · subtitles · recommended", "srt"),
    ("WebVTT · web/video players", "vtt"),
    ("TXT · transcript only", "txt"),
    ("CSV · timestamps + text", "csv"),
]


def _vtt_timestamp(milliseconds: int) -> str:
    return format_timestamp(milliseconds).replace(",", ".")


def segments_to_vtt(segments: list[Segment]) -> str:
    blocks = ["WEBVTT", ""]
    for segment in segments:
        blocks.extend(
            [
                f"{_vtt_timestamp(segment.start_ms)} --> {_vtt_timestamp(segment.end_ms)}",
                segment.text.strip(),
                "",
            ]
        )
    return "\n".join(blocks).rstrip() + "\n"


def segments_to_txt(segments: list[Segment]) -> str:
    return "\n".join(segment.text.strip() for segment in segments if segment.text.strip()) + "\n"


def segments_to_csv(segments: list[Segment]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["start", "end", "text"])
    for segment in segments:
        writer.writerow(
            [
                format_timestamp(segment.start_ms),
                format_timestamp(segment.end_ms),
                segment.text.strip(),
            ]
        )
    return stream.getvalue()


def export_subtitle_timeline(subtitle_path: str | Path, output_format: str = "srt") -> Path:
    """Export DubLocal's normalized SRT timeline without rerunning transcription."""

    source = Path(subtitle_path).expanduser().resolve()
    if not source.is_file():
        raise DubLocalError("The subtitle timeline is no longer available. Extract or transcribe it again.")

    try:
        segments = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not read the subtitle timeline: {exc}") from exc
    if not segments:
        raise DubLocalError("The subtitle timeline contains no timed text to export.")

    fmt = str(output_format or "srt").strip().lower()
    serializers = {
        "srt": lambda items: segments_to_srt(items),
        "vtt": segments_to_vtt,
        "txt": segments_to_txt,
        "csv": segments_to_csv,
    }
    if fmt not in serializers:
        raise DubLocalError(f"Unsupported subtitle export format: {output_format}")

    if fmt == "srt":
        return source

    output_dir = _new_job_dir("subtitle-export")
    output = output_dir / f"captions.{fmt}"
    output.write_text(serializers[fmt](segments), encoding="utf-8")
    return output
