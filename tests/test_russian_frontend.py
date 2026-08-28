from __future__ import annotations

import unicodedata

from dublocal.russian_frontend import _integer_to_russian, _normalize_input_text


def test_zero_width_joiner_before_digit_is_removed_and_digit_is_spoken():
    assert _normalize_input_text("\u200d2") == "два"


def test_web_caption_format_controls_do_not_survive_russian_normalization():
    value = _normalize_input_text("Привет\u200b\u200d 12\ufeff раз")
    assert value == "Привет двенадцать раз"
    assert not any(unicodedata.category(char) == "Cf" for char in value)


def test_russian_number_expansion_handles_cardinals_signs_and_decimals():
    assert _integer_to_russian(2026) == "две тысячи двадцать шесть"
    assert _normalize_input_text("-12") == "минус двенадцать"
    assert _normalize_input_text("3.14") == "три запятая один четыре"
