from __future__ import annotations

import numpy as np

from dublocal.voice_match import (
    AUTO_VOICE_VALUE,
    auto_default_voice,
    auto_voice_choices,
    estimate_fundamental_hz,
    vocal_range_label,
)


def _tone(hz: float, seconds: float = 1.5, rate: int = 8000) -> np.ndarray:
    t = np.arange(int(seconds * rate), dtype=np.float32) / rate
    return (0.35 * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def test_fundamental_estimator_separates_lower_and_higher_vocal_ranges():
    lower = estimate_fundamental_hz(_tone(115.0))
    higher = estimate_fundamental_hz(_tone(225.0))
    assert lower is not None and 100.0 <= lower <= 130.0
    assert higher is not None and 205.0 <= higher <= 245.0
    assert vocal_range_label(lower) == "lower"
    assert vocal_range_label(higher) == "higher"


def test_auto_voice_is_default_when_language_has_choices():
    choices = auto_voice_choices("en-US")
    assert choices[0] == (AUTO_VOICE_VALUE, AUTO_VOICE_VALUE)
    assert auto_default_voice("en-US") == AUTO_VOICE_VALUE
    assert auto_default_voice("ru") is None
