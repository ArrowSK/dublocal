from __future__ import annotations

from pathlib import Path
from typing import Any

from . import transcription
from .media import DubLocalError


# Silero VAD is designed for speech detection and can reject sustained singing.
# DubLocal's Accurate Whisper profile is explicitly recommended for music videos,
# so that profile keeps Whisper's own decoder path rather than forcing VAD first.
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


def _output_prefix(command: list[str]) -> Path | None:
    try:
        return Path(command[command.index("-of") + 1])
    except (ValueError, IndexError):
        return None


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


def _run_with_vad_fallback(command: list[str]) -> None:
    """Retry one Whisper job without VAD when the VAD pass cannot produce subtitles.

    The retry reuses the already downloaded/prepared WAV and model, so YouTube media is
    not fetched a second time. This specifically protects against whisper.cpp/Silero
    combinations that exit successfully but emit no SRT, as seen with some music-heavy
    material.
    """

    if "--vad" not in command:
        _ORIGINAL_RUN(command)
        return

    fallback = _without_vad(command)
    try:
        _ORIGINAL_RUN(command)
    except DubLocalError as first_error:
        _clear_partial_outputs(command)
        try:
            _ORIGINAL_RUN(fallback)
        except DubLocalError as fallback_error:
            raise DubLocalError(
                "Whisper's speech-detector pass failed and the automatic non-VAD retry "
                f"also failed: {fallback_error}"
            ) from fallback_error
        return

    if _srt_ready(command):
        return

    _clear_partial_outputs(command)
    _ORIGINAL_RUN(fallback)


def _transcribe_with_media_policy(
    info: dict[str, Any],
    model_id: str = "base",
    language: str = "auto",
):
    if model_id != _SINGING_FRIENDLY_MODEL:
        return _ORIGINAL_TRANSCRIBE(info, model_id=model_id, language=language)

    # Accurate/Large-v3-Turbo is the UI's song/music-video recommendation. Silero VAD
    # can classify singing as non-speech, so do not gate this profile through VAD.
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
