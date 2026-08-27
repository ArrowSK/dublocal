from dublocal.language_utils import normalize_language_code


def test_language_normalization_accepts_whisper_names_and_iso_codes():
    assert normalize_language_code("en") == "en"
    assert normalize_language_code("English") == "en"
    assert normalize_language_code("Spanish") == "es"
    assert normalize_language_code("русский") == "auto"  # unsupported free-form alias is conservative
    assert normalize_language_code("pt-BR") == "pt"
    assert normalize_language_code("auto") == "auto"
