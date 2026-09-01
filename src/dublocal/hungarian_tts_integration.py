from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import tts, voice_match
from .hungarian_tts import (
    HUNGARIAN_LANGUAGE,
    generate_hungarian_voice_track,
    hungarian_status_text,
    install_hungarian_metadata,
    is_macos_system_voice,
    prepare_hungarian_tts,
)
from .media import DubLocalError


_INSTALLED = False


def install_hungarian_tts_integration() -> None:
    """Add Hungarian behind the stable DubLocal TTS interface.

    Provider/refinement installation order matters in DubLocal. This function is called
    after the existing Kokoro/Russian provider layer and before native timing captures
    the final synthesis function, so Hungarian does not replace or redesign any
    established provider path.
    """

    global _INSTALLED
    if _INSTALLED:
        return

    original_generate = tts.generate_voice_track
    original_prepare = tts.prepare_kokoro
    original_status = tts.kokoro_runtime_status
    original_resolve_auto_voice = voice_match.resolve_auto_voice_plan

    install_hungarian_metadata()

    def generate_voice_track_with_hungarian(
        subtitle_path: str | Path,
        *,
        language: str,
        voice: str,
        speed: float = 1.0,
        segment_voices: dict[int, str] | None = None,
    ):
        if language == HUNGARIAN_LANGUAGE:
            return generate_hungarian_voice_track(
                subtitle_path,
                voice=voice,
                speed=float(speed),
                segment_voices=segment_voices,
            )
        return original_generate(
            subtitle_path,
            language=language,
            voice=voice,
            speed=float(speed),
            segment_voices=segment_voices,
        )

    def prepare_voice_engine_with_hungarian(
        language: str,
        voice: str,
        speed: float = 1.0,
    ) -> str:
        if language == HUNGARIAN_LANGUAGE:
            return prepare_hungarian_tts(voice, float(speed))
        return original_prepare(language, voice, float(speed))

    def voice_engine_status_with_hungarian() -> str:
        return original_status() + "\n" + hungarian_status_text()

    def resolve_auto_voice_with_hungarian(
        subtitle_path: str | Path,
        source_info: dict[str, Any] | None,
        language: str,
        *,
        progress_callback=None,
    ):
        # On macOS the system Hungarian voice is the deliberate Auto preference.
        # Do not let the generic lower/higher preset matcher silently replace it with
        # Piper. Users can still select Anna/Berta/Imre explicitly. On Windows and
        # other platforms there is no system voice, so the established matcher can use
        # the Piper female/male pair normally.
        if language == HUNGARIAN_LANGUAGE:
            default = tts.kokoro_default_voice(language)
            if default and is_macos_system_voice(default):
                return default, {}, "macOS system Hungarian voice"
        return original_resolve_auto_voice(
            subtitle_path,
            source_info,
            language,
            progress_callback=progress_callback,
        )

    tts.generate_voice_track = generate_voice_track_with_hungarian
    tts.prepare_kokoro = prepare_voice_engine_with_hungarian
    tts.kokoro_runtime_status = voice_engine_status_with_hungarian
    voice_match.resolve_auto_voice_plan = resolve_auto_voice_with_hungarian

    # magic_flow is imported early by output-profile compatibility layers and keeps a
    # by-value reference to voice matching. Update that one known compatibility
    # reference when it is already loaded; future imports see voice_match directly.
    magic_flow = sys.modules.get("dublocal.magic_flow")
    if magic_flow is not None:
        setattr(magic_flow, "resolve_auto_voice_plan", resolve_auto_voice_with_hungarian)

    _INSTALLED = True
