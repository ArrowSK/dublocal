from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dublocal.transcription as transcription
import dublocal.transcription_v053 as smart
from dublocal.timeline import Segment, parse_srt, segments_to_srt


def test_m1_budget_limits_selective_recovery(monkeypatch):
    monkeypatch.setattr(
        smart,
        "detect_hardware_profile",
        lambda: SimpleNamespace(apple_silicon=True, intel_mac=False, memory_gib=8.0),
    )
    assert smart._recovery_budget() == (3, 24_000)


def test_gap_candidates_exist_only_for_accurate_profile():
    segments = [
        Segment(1, 0, 3_000, "This is a real line."),
        Segment(2, 5_000, 8_000, "This is the next line."),
    ]
    accurate = smart._candidate_regions(segments, "large-v3-turbo-q5_0")
    base = smart._candidate_regions(segments, "base")
    assert any(item.kind == "gap" for item in accurate)
    assert not any(item.kind == "gap" for item in base)


def test_verified_gap_recovery_rejects_echo_of_neighbour(monkeypatch, tmp_path: Path):
    srt = tmp_path / "captions.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello there.\n", encoding="utf-8")
    result = transcription.TranscriptionResult(
        srt_path=srt,
        segments=[],
        model_id="large-v3-turbo-q5_0",
        language="en",
        vad_used=False,
    )
    region = smart._RecoveryRegion(
        kind="gap",
        start_ms=1_000,
        end_ms=3_000,
        left_text="Lost at the sight of your blood.",
        right_text="The next real lyric starts now.",
    )
    echoed = [Segment(1, 1_200, 2_800, "Lost at the sight of your blood.")]
    monkeypatch.setattr(smart, "_run_isolated", lambda *args, **kwargs: echoed)

    assert smart._verified_recovery(result, tmp_path / "speech.wav", region, 1) is None


def test_verified_sparse_recovery_requires_two_pass_consensus_and_more_words(monkeypatch, tmp_path: Path):
    srt = tmp_path / "captions.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:05,000\nMy hands shake.\n", encoding="utf-8")
    result = transcription.TranscriptionResult(
        srt_path=srt,
        segments=[],
        model_id="large-v3-turbo-q5_0",
        language="en",
        vad_used=False,
    )
    region = smart._RecoveryRegion(
        kind="sparse",
        start_ms=0,
        end_ms=5_350,
        segment_index=1,
        original_text="My hands shake.",
    )
    replies = iter(
        [
            [Segment(1, 0, 5_000, "My hands are always shaking in the dark.")],
            [Segment(1, 0, 5_000, "My hands are always shaking in the dark.")],
        ]
    )
    monkeypatch.setattr(smart, "_run_isolated", lambda *args, **kwargs: next(replies))

    recovered = smart._verified_recovery(result, tmp_path / "speech.wav", region, 1)
    assert recovered is not None
    assert "always shaking" in recovered[0].text


def test_smart_wrapper_writes_only_verified_recoveries(monkeypatch, tmp_path: Path):
    srt = tmp_path / "captions.srt"
    wav = tmp_path / "speech-16k-mono.wav"
    wav.write_bytes(b"wav")
    original = [
        Segment(1, 0, 5_000, "My hands shake."),
        Segment(2, 5_500, 8_000, "Next normal line here."),
    ]
    srt.write_text(segments_to_srt(original), encoding="utf-8")
    base_result = transcription.TranscriptionResult(
        srt_path=srt,
        segments=original,
        model_id="large-v3-turbo-q5_0",
        language="en",
        vad_used=False,
    )

    monkeypatch.setattr(smart, "_ORIGINAL_TRANSCRIBE", lambda info, model_id="base", language="auto": base_result)
    monkeypatch.setattr(smart, "_recovery_budget", lambda: (2, 20_000))
    monkeypatch.setattr(
        smart,
        "_candidate_regions",
        lambda segments, model_id: [
            smart._RecoveryRegion(
                kind="sparse",
                start_ms=0,
                end_ms=5_350,
                segment_index=1,
                original_text="My hands shake.",
            )
        ],
    )
    monkeypatch.setattr(
        smart,
        "_verified_recovery",
        lambda result, wav_path, region, ordinal: [
            Segment(1, 0, 5_000, "My hands are always shaking in the dark.")
        ],
    )

    result = smart._transcribe_with_smart_recovery({}, model_id="large-v3-turbo-q5_0")
    cleaned = parse_srt(result.srt_path.read_text(encoding="utf-8"))
    assert cleaned[0].text == "My hands are always shaking in the dark."
    assert cleaned[1].text == "Next normal line here."
