from __future__ import annotations

from dublocal import tts
from dublocal.tts_provider_refinement import _apply_provider_metadata
from dublocal.ui_v062 import build_app


def test_v062_ui_builds_with_russian_provider_controls() -> None:
    snapshot = (
        dict(tts.KOKORO_LANGUAGES),
        list(tts.KOKORO_LANGUAGE_CHOICES),
        dict(tts._PREPARE_TEXT),
        dict(tts._TRANSLATION_TO_KOKORO),
    )
    try:
        _apply_provider_metadata()
        demo = build_app()
        assert demo is not None
    finally:
        languages, choices, prepare_text, translation_map = snapshot
        tts.KOKORO_LANGUAGES.clear()
        tts.KOKORO_LANGUAGES.update(languages)
        tts.KOKORO_LANGUAGE_CHOICES[:] = choices
        tts._PREPARE_TEXT.clear()
        tts._PREPARE_TEXT.update(prepare_text)
        tts._TRANSLATION_TO_KOKORO.clear()
        tts._TRANSLATION_TO_KOKORO.update(translation_map)
