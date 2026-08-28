from __future__ import annotations


def install_language_extensions() -> None:
    """Expose Ukrainian and Bulgarian consistently across translation UI/runtime.

    Ukrainian was already present in the core translation registry. This keeps that
    route explicit and adds Bulgarian without implying that either language has a
    vetted Kokoro TTS provider.
    """

    from . import app, language_utils, m5, translation

    translation.TRANSLATION_LANGUAGES.setdefault("uk", {"label": "Ukrainian", "opus": "ukr"})
    translation.TRANSLATION_LANGUAGES.setdefault("bg", {"label": "Bulgarian", "opus": "bul"})
    translation._LANGUAGE_ALIASES.update(
        {
            "ukr": "uk",
            "uk": "uk",
            "bul": "bg",
            "bg": "bg",
        }
    )
    language_utils._LANGUAGE_ALIASES.update(
        {
            "ukr": "uk",
            "ukrainian": "uk",
            "українська": "uk",
            "uk": "uk",
            "bul": "bg",
            "bulgarian": "bg",
            "български": "bg",
            "bg": "bg",
        }
    )
    m5._ISO639_2.setdefault("uk", "ukr")
    m5._ISO639_2.setdefault("bg", "bul")

    # app.py derives target choices from the registry at import time. Refresh the
    # existing list object so already-imported UI modules also see the new language.
    app.TARGET_LANGUAGE_CHOICES[:] = [
        (metadata["label"], code)
        for code, metadata in translation.TRANSLATION_LANGUAGES.items()
    ]

    source_choices = list(app.LANGUAGE_CHOICES)
    if not any(value == "uk" for _label, value in source_choices):
        source_choices.append(("Ukrainian", "uk"))
    if not any(value == "bg" for _label, value in source_choices):
        source_choices.append(("Bulgarian", "bg"))
    app.LANGUAGE_CHOICES[:] = source_choices
