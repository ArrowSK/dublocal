from __future__ import annotations


_LANGUAGE_ALIASES = {
    "eng": "en",
    "english": "en",
    "en": "en",
    "hun": "hu",
    "hungarian": "hu",
    "magyar": "hu",
    "hu": "hu",
    "rus": "ru",
    "russian": "ru",
    "ru": "ru",
    "deu": "de",
    "ger": "de",
    "german": "de",
    "deutsch": "de",
    "de": "de",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "français": "fr",
    "francais": "fr",
    "fr": "fr",
    "spa": "es",
    "spanish": "es",
    "español": "es",
    "espanol": "es",
    "es": "es",
    "ita": "it",
    "italian": "it",
    "italiano": "it",
    "it": "it",
    "por": "pt",
    "portuguese": "pt",
    "português": "pt",
    "portugues": "pt",
    "pt": "pt",
    "pol": "pl",
    "polish": "pl",
    "polski": "pl",
    "pl": "pl",
    "ukr": "uk",
    "ukrainian": "uk",
    "українська": "uk",
    "uk": "uk",
    "srp": "sr",
    "serbian": "sr",
    "sr": "sr",
    "hrv": "hr",
    "croatian": "hr",
    "hr": "hr",
}


def normalize_language_code(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    if not raw or raw in {"auto", "und", "unknown", "undefined"}:
        return "auto"
    candidates = [raw, raw.split("-", 1)[0]]
    for candidate in candidates:
        if candidate in _LANGUAGE_ALIASES:
            return _LANGUAGE_ALIASES[candidate]
    return "auto"
