from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from dublocal.media import DubLocalError
from dublocal.timeline import Segment
from dublocal.tts import (
    VoiceSegmentResult,
    _assemble_voice_track,
    _validate_kokoro_selection,
    kokoro_default_voice,
    kokoro_voice_choices,
    suggested_kokoro_language,
)


def _write_tone(path: Path, *, frames: int, value: int = 4000, rate: int = 24000) -> None:
    data = np.full(frames, value, dtype="<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(data.tobytes())


def test_translation_language_suggestions_are_explicit():
    assert suggested_kokoro_language("en") == "en-US"
    assert suggested_kokoro_language("fr") == "fr"
    assert suggested_kokoro_language("pt") == "pt-BR"
    assert suggested_kokoro_language("hu") is None
    assert suggested_kokoro_language("ru") is None


def test_voice_inventory_follows_language_frontend():
    assert kokoro_default_voice("en-US") == "af_heart"
    assert kokoro_default_voice("en-GB") == "bf_emma"
    assert ("George · male", "bm_george") in kokoro_voice_choices("en-GB")

    with pytest.raises(DubLocalError):
        _validate_kokoro_selection("en-GB", "af_heart", 1.0)


def test_voice_track_assembly_preserves_subtitle_start_times(tmp_path: Path):
    first_wav = tmp_path / "first.wav"
    second_wav = tmp_path / "second.wav"
    _write_tone(first_wav, frames=2400, value=3000)  # 100 ms
    _write_tone(second_wav, frames=2400, value=5000)  # 100 ms

    timeline = [
        Segment(index=1, start_ms=0, end_ms=200, text="One"),
        Segment(index=2, start_ms=500, end_ms=700, text="Two"),
    ]
    generated = [
        VoiceSegmentResult(1, 0, 200, "One", 100, 200, 0, first_wav),
        VoiceSegmentResult(2, 500, 700, "Two", 100, 200, 0, second_wav),
    ]
    output = tmp_path / "track.wav"

    _assemble_voice_track(timeline, generated, output)

    with wave.open(str(output), "rb") as handle:
        assert handle.getframerate() == 24000
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")

    assert np.max(np.abs(pcm[:2400])) > 0
    assert np.max(np.abs(pcm[2400:12000])) == 0
    assert np.max(np.abs(pcm[12000:14400])) > 0


def test_voice_track_assembly_mixes_overlapping_segments(tmp_path: Path):
    first_wav = tmp_path / "first.wav"
    second_wav = tmp_path / "second.wav"
    _write_tone(first_wav, frames=4800, value=2000)  # 200 ms
    _write_tone(second_wav, frames=4800, value=3000)  # 200 ms

    timeline = [
        Segment(index=1, start_ms=0, end_ms=100, text="One"),
        Segment(index=2, start_ms=100, end_ms=300, text="Two"),
    ]
    generated = [
        VoiceSegmentResult(1, 0, 100, "One", 200, 100, 100, first_wav),
        VoiceSegmentResult(2, 100, 300, "Two", 200, 200, 0, second_wav),
    ]
    output = tmp_path / "overlap.wav"

    _assemble_voice_track(timeline, generated, output)

    with wave.open(str(output), "rb") as handle:
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")

    # At 100-200 ms both clips are present, so the mixed level is higher than
    # either input alone. M5 will later fit durations to avoid this situation.
    overlap = pcm[2400:4800]
    assert int(np.median(overlap)) > 3000
