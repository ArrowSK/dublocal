from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dublocal import adaptive_audio
from dublocal.hardware_profile import HardwareProfile
from dublocal.kokoro_worker import _native_speed_for_target
from dublocal.source_separation import recommend_separation_profile


def _profile(memory_gib: int) -> HardwareProfile:
    return HardwareProfile(
        architecture="arm64",
        memory_bytes=memory_gib * 1024**3,
        cpu_name="Apple test chip",
        system_name="Darwin",
    )


def test_adaptive_timing_never_slows_a_line_that_already_fits() -> None:
    assert _native_speed_for_target(1.0, 3000, 5000) == 1.0
    assert _native_speed_for_target(0.8, 3000, 5000) == 0.8


def test_adaptive_timing_speeds_up_overflow() -> None:
    speed = _native_speed_for_target(1.0, 5000, 3000)
    assert 1.6 < speed < 1.7


def test_separation_profile_protects_8gb_apple_silicon() -> None:
    profile = recommend_separation_profile(_profile(8))
    assert profile.model == "htdemucs"
    assert profile.segment_seconds <= 4.0
    assert profile.device == "cpu"


def test_high_memory_profile_can_use_finetuned_separation() -> None:
    profile = recommend_separation_profile(_profile(32))
    assert profile.model == "htdemucs_ft"
    assert profile.segment_seconds <= 7.8


def test_music_cues_are_a_strong_auto_signal(tmp_path: Path) -> None:
    srt = tmp_path / "song.srt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\n♪ Hello, hello ♪\n",
        encoding="utf-8",
    )
    score = adaptive_audio.music_signal_score(
        {"title": "Example", "uploader": "Example"},
        srt,
    )
    assert score >= 3.5


def test_auto_music_falls_back_when_separation_is_not_prepared(monkeypatch, tmp_path: Path) -> None:
    srt = tmp_path / "song.srt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\n♪ Hello ♪\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(adaptive_audio, "separation_runtime", lambda: None)
    plan = adaptive_audio.resolve_mix_plan({"title": "Official Music Video"}, srt, "auto")
    assert plan.resolved == "dialogue"
    assert plan.music_score >= 3.5


def test_explicit_separation_remains_available_without_prepared_runtime(monkeypatch) -> None:
    monkeypatch.setattr(adaptive_audio, "separation_runtime", lambda: None)
    plan = adaptive_audio.resolve_mix_plan({}, None, "separated")
    assert plan.resolved == "separated"


def test_v061_ui_composes_without_mutating_the_test_process() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from dublocal.ui_v061 import build_app; assert build_app() is not None",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
