from __future__ import annotations

import re
import tempfile
from pathlib import Path

from platformdirs import user_cache_dir

from .media import DubLocalError
from .timeline import Segment, parse_srt, segments_to_srt


_BRACKETED_CUE_RE = re.compile(r"\s*\[[^\]\r\n]{1,120}\]\s*")
_SPACE_RE = re.compile(r"[ \t]{2,}")


def spoken_text(text: str) -> str:
    """Remove closed-caption cues from text that will be spoken by TTS.

    The subtitle itself is not modified. Only the temporary voice-input timeline is
    cleaned, so cues such as ``[MUSIC]`` remain present in SRT/VTT exports while
    Kokoro never says "music" aloud.
    """

    value = _BRACKETED_CUE_RE.sub(" ", text or "")
    value = _SPACE_RE.sub(" ", value)
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return "\n".join(lines).strip()


def voice_segments(segments: list[Segment]) -> list[Segment]:
    cleaned: list[Segment] = []
    for segment in segments:
        text = spoken_text(segment.text)
        if not text:
            continue
        cleaned.append(
            Segment(
                index=segment.index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=text,
            )
        )
    return cleaned


def prepare_voice_srt(subtitle_path: str | Path) -> Path:
    source = Path(subtitle_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".srt":
        raise DubLocalError("Voice generation requires a generated or imported SRT timeline.")
    try:
        timeline = parse_srt(source.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not parse the subtitle timeline for voice generation: {exc}") from exc

    cleaned = voice_segments(timeline)
    if not cleaned:
        raise DubLocalError(
            "The subtitle timeline contains only non-spoken caption cues, so there is nothing to voice."
        )

    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    job_dir = Path(tempfile.mkdtemp(prefix="voice-input-", dir=root))
    output = job_dir / "voice-input.srt"
    output.write_text(segments_to_srt(cleaned), encoding="utf-8")
    return output
