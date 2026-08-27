from __future__ import annotations

import json
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from .media import DubLocalError
from .timeline import parse_srt
from .transcription import (
    WHISPER_MODELS,
    TranscriptionResult,
    WhisperEngineMissingError,
    WhisperModelMissingError,
    _convert_to_whisper_wav,
    _detected_language,
    _new_job_dir,
    _source_media_path,
    _whisper_environment,
    find_whisper_cli,
    whisper_model_path,
)


ProgressCallback = Callable[[float, str], None]
_PROGRESS_RE = re.compile(r"progress\s*=\s*(\d{1,3})%", re.IGNORECASE)


def transcribe_source_with_progress(
    info: dict[str, Any],
    model_id: str = "base",
    language: str = "auto",
    *,
    progress_callback: ProgressCallback | None = None,
) -> TranscriptionResult:
    executable = find_whisper_cli()
    if not executable:
        raise WhisperEngineMissingError(
            "The local whisper.cpp engine is not installed. Rerun the DubLocal launcher installer and allow whisper.cpp installation."
        )

    model = whisper_model_path(model_id)
    if not model.is_file():
        metadata = WHISPER_MODELS[model_id]
        raise WhisperModelMissingError(
            f"Whisper {model_id} is not installed ({metadata['size']}). Install it in Settings → Model Manager first."
        )

    job_dir = _new_job_dir("transcription")
    if progress_callback:
        progress_callback(0.02, "Acquiring source audio")
    source = _source_media_path(info, job_dir)

    if progress_callback:
        progress_callback(0.08, "Preparing 16 kHz speech audio")
    wav = _convert_to_whisper_wav(source, job_dir)

    output_prefix = job_dir / "captions"
    requested_language = (language or "auto").strip().lower()
    command = [
        executable,
        "-m",
        str(model),
        "-f",
        str(wav),
        "-osrt",
        "-oj",
        "-of",
        str(output_prefix),
        "-l",
        requested_language,
        "-pp",
    ]
    if platform.machine().lower() in {"x86_64", "amd64"}:
        command.append("-ng")

    if progress_callback:
        progress_callback(0.15, "Transcribing speech with whisper.cpp")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_whisper_environment(),
        )
    except OSError as exc:
        raise DubLocalError(f"Could not start whisper.cpp: {exc}") from exc

    captured: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        captured.append(line)
        match = _PROGRESS_RE.search(line)
        if match and progress_callback:
            percent = max(0, min(100, int(match.group(1))))
            fraction = 0.15 + 0.82 * (percent / 100.0)
            progress_callback(fraction, f"Transcribing speech · whisper.cpp {percent}%")

    return_code = process.wait()
    if return_code != 0:
        detail = "".join(captured).strip()
        raise DubLocalError(
            "Local Whisper transcription failed: "
            + (detail.splitlines()[-1] if detail else f"exit code {return_code}")
        )

    if progress_callback:
        progress_callback(0.98, "Finalizing subtitle timeline")

    srt_path = output_prefix.with_suffix(".srt")
    if not srt_path.is_file() or srt_path.stat().st_size == 0:
        raise DubLocalError("whisper.cpp completed but did not create an SRT subtitle file.")

    text = srt_path.read_text(encoding="utf-8", errors="replace")
    try:
        segments = parse_srt(text)
    except ValueError as exc:
        raise DubLocalError(f"Whisper created an invalid subtitle timeline: {exc}") from exc
    if not segments:
        raise DubLocalError("Whisper produced an empty transcription.")

    if progress_callback:
        progress_callback(1.0, "Transcription complete")

    return TranscriptionResult(
        srt_path=srt_path,
        segments=segments,
        model_id=model_id,
        language=_detected_language(output_prefix, requested_language),
    )
