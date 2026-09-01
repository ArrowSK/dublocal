from __future__ import annotations

from pathlib import Path
from typing import Any

from . import tts
from .hungarian_tts import (
    HUNGARIAN_LANGUAGE,
    generate_hungarian_voice_track,
    hungarian_default_voice,
    hungarian_status_text,
    hungarian_voice_choices,
    prepare_hungarian_tts,
)
from .media import DubLocalError
from .tts_provider_refinement import (
    generate_voice_track_provider_aware,
    prepare_kokoro_provider_aware,
)
from .tts_provider_registry import (
    all_providers,
    provider_for_language,
    provider_is_installed,
    provider_status_text,
)


# The core Kokoro module is intentionally limited to the official upstream model.
# This module is the one explicit composition boundary for official Kokoro, local
# third-party providers and the platform-aware Hungarian engine.


def _normalise_language(value: str | None) -> str:
    return str(value or "").strip().replace("_", "-")


def _provider_language_choices() -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    seen: set[str] = set()
    for provider in all_providers():
        language = _normalise_language(provider.language)
        if not language or language in seen or language in tts.KOKORO_LANGUAGES:
            continue
        # Russian is intentionally visible before preparation so Model Manager can
        # guide first-time setup. Other custom languages are visible only once their
        # vetted provider is prepared, preserving official-Kokoro behavior otherwise.
        if language != "ru" and not provider_is_installed(provider):
            continue
        seen.add(language)
        label = str(provider.manifest.get("language_label") or language)
        choices.append((label, language))
    return choices


def voice_language_choices() -> list[tuple[str, str]]:
    choices = [
        (str(metadata["label"]), code)
        for code, metadata in tts.KOKORO_LANGUAGES.items()
    ]
    known = {value for _label, value in choices}
    for label, language in _provider_language_choices():
        if language not in known:
            choices.append((label, language))
            known.add(language)
    if HUNGARIAN_LANGUAGE not in known:
        choices.append(("Hungarian", HUNGARIAN_LANGUAGE))
    return choices


def _provider_for_explicit_language(language: str, *, require_installed: bool):
    provider = provider_for_language(language, require_installed=require_installed)
    if provider is None:
        return None
    # Official Kokoro remains the default for its native languages unless a custom
    # provider explicitly declares itself preferred. Russian has no official route.
    if language in tts.KOKORO_LANGUAGES and not provider.manifest.get("preferred"):
        return None
    return provider


def voice_choices(language: str | None) -> list[tuple[str, str]]:
    selected = _normalise_language(language)
    if selected == HUNGARIAN_LANGUAGE:
        return hungarian_voice_choices()

    provider = _provider_for_explicit_language(selected, require_installed=False)
    if provider is not None:
        if selected == "ru" or provider_is_installed(provider):
            return [
                (str(item.get("label") or item.get("id") or "Voice"), str(item["id"]))
                for item in provider.voices
                if item.get("id")
            ]

    return tts.kokoro_voice_choices(selected)


def default_voice(language: str | None) -> str | None:
    selected = _normalise_language(language)
    if selected == HUNGARIAN_LANGUAGE:
        return hungarian_default_voice()

    provider = _provider_for_explicit_language(selected, require_installed=False)
    if provider is not None and (selected == "ru" or provider_is_installed(provider)):
        return str(provider.manifest.get("default_voice") or "") or None
    return tts.kokoro_default_voice(selected)


def suggested_voice_language(language: str | None) -> str | None:
    value = _normalise_language(language)
    if not value:
        return None
    base = value.casefold().split("-", 1)[0]
    if base == "hu":
        return HUNGARIAN_LANGUAGE
    if base == "ru":
        return "ru"

    official = tts.suggested_kokoro_language(value)
    if official is not None:
        return official

    # Prepared custom providers may extend the voice language catalogue without
    # mutating Kokoro's global metadata tables.
    for provider in all_providers():
        provider_language = _normalise_language(provider.language)
        if provider_language.casefold().split("-", 1)[0] == base and provider_is_installed(provider):
            return provider_language
    return None


def prepare_voice_engine(language: str, voice: str, speed: float = 1.0) -> str:
    selected = _normalise_language(language)
    if selected == HUNGARIAN_LANGUAGE:
        return prepare_hungarian_tts(voice, float(speed))

    provider = _provider_for_explicit_language(selected, require_installed=False)
    if provider is not None:
        return prepare_kokoro_provider_aware(selected, voice, float(speed))
    return tts.prepare_kokoro(selected, voice, float(speed))


def generate_voice_track(
    subtitle_path: str | Path,
    *,
    language: str,
    voice: str,
    speed: float = 1.0,
    segment_voices: dict[int, str] | None = None,
):
    selected = _normalise_language(language)
    if selected == HUNGARIAN_LANGUAGE:
        return generate_hungarian_voice_track(
            subtitle_path,
            voice=voice,
            speed=float(speed),
            segment_voices=segment_voices,
        )

    provider = _provider_for_explicit_language(selected, require_installed=True)
    if provider is not None:
        return generate_voice_track_provider_aware(
            subtitle_path,
            language=selected,
            voice=voice,
            speed=float(speed),
            segment_voices=segment_voices,
        )

    registered = _provider_for_explicit_language(selected, require_installed=False)
    if registered is not None and selected not in tts.KOKORO_LANGUAGES:
        raise DubLocalError(
            f"{registered.label} is registered for {selected} but is not prepared. "
            "Open Settings → Model Manager and prepare the TTS provider first."
        )

    return tts.generate_voice_track(
        subtitle_path,
        language=selected,
        voice=voice,
        speed=float(speed),
        segment_voices=segment_voices,
    )


def voice_engine_status() -> str:
    return (
        tts.kokoro_runtime_status()
        + "\n"
        + provider_status_text()
        + "\n"
        + hungarian_status_text()
    )


def voice_language_metadata(language: str | None) -> dict[str, Any]:
    """Return UI-facing voice metadata without mutating another module's globals."""

    selected = _normalise_language(language)
    choices = voice_choices(selected)
    if selected == HUNGARIAN_LANGUAGE:
        return {
            "label": "Hungarian",
            "default_voice": default_voice(selected),
            "voices": choices,
            "provider_id": "hungarian-local-auto",
        }

    provider = _provider_for_explicit_language(selected, require_installed=False)
    if provider is not None and (selected == "ru" or provider_is_installed(provider)):
        return {
            "label": str(provider.manifest.get("language_label") or selected),
            "default_voice": default_voice(selected),
            "voices": choices,
            "provider_id": provider.id,
        }

    metadata = tts.KOKORO_LANGUAGES.get(selected)
    return dict(metadata) if metadata else {}
