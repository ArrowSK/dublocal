from __future__ import annotations

from pathlib import Path

import dublocal.transcription_guard as guard
from dublocal.timeline import Segment, parse_srt, segments_to_srt


def test_vad_run_retries_same_job_without_vad_when_no_srt(tmp_path: Path):
    calls: list[list[str]] = []
    output_prefix = tmp_path / "captions"

    def fake_run(command: list[str]) -> None:
        calls.append(list(command))
        if "--vad" not in command:
            output_prefix.with_suffix(".srt").write_text(
                "1\n00:00:28,000 --> 00:00:30,000\nHello.\n",
                encoding="utf-8",
            )

    command = [
        "whisper-cli",
        "-m",
        "model.bin",
        "-f",
        "speech.wav",
        "-osrt",
        "-of",
        str(output_prefix),
        "--vad",
        "--vad-model",
        "vad.bin",
        "--vad-threshold",
        "0.45",
    ]
    guard.run_whisper_guarded(command, runner=fake_run)

    assert len(calls) == 2
    assert "--vad" in calls[0]
    assert "--vad" not in calls[1]
    assert "--vad-model" not in calls[1]
    assert output_prefix.with_suffix(".srt").is_file()


def test_accurate_command_disables_rolling_context_and_raises_entropy_guard():
    command = [
        "whisper-cli",
        "-m",
        "/models/ggml-large-v3-turbo-q5_0.bin",
        "-f",
        "speech.wav",
        "-mc",
        "64",
        "-nth",
        "0.50",
    ]
    prepared = guard._prepare_command(command)
    assert prepared[prepared.index("-mc") + 1] == "0"
    assert prepared[prepared.index("-et") + 1] == "2.60"


def test_base_command_keeps_normal_context_policy():
    command = [
        "whisper-cli",
        "-m",
        "/models/ggml-base.bin",
        "-f",
        "speech.wav",
        "-mc",
        "64",
        "-nth",
        "0.50",
    ]
    prepared = guard._prepare_command(command)
    assert prepared[prepared.index("-mc") + 1] == "64"
    assert "-et" not in prepared


def test_repeat_detector_catches_near_duplicate_intro_and_long_loop():
    segments = [
        Segment(1, 0, 7000, "I am not sure if you have any questions yet, but I am not sure."),
        Segment(2, 7000, 14000, "I am not sure if you have any questions yet."),
        Segment(3, 14000, 17000, "I am not sure if you have any questions yet."),
        Segment(4, 17000, 20000, "I am not sure if you have any questions yet."),
        Segment(5, 20000, 24000, "I am not sure if you have any questions yet."),
        Segment(6, 24000, 28000, "I am not sure if you have any questions yet."),
        Segment(7, 28000, 32000, "Actual lyric begins here."),
    ]
    for index in range(8, 20):
        start = 32_000 + (index - 8) * 3_000
        segments.append(Segment(index, start, start + 3_000, "The same invented phrase again."))

    runs = guard._find_repeat_runs(segments)
    assert len(runs) == 2
    assert runs[0].count == 6
    assert runs[0].start_ms == 0
    assert runs[1].count == 12
    assert runs[1].severe is True


def test_repetition_guard_replaces_suspicious_intro_with_isolated_retry(tmp_path: Path):
    prefix = tmp_path / "captions"
    original = [
        Segment(1, 0, 5000, "I am not sure if you have questions."),
        Segment(2, 5000, 10000, "I am not sure if you have questions."),
        Segment(3, 10000, 15000, "I am not sure if you have questions."),
        Segment(4, 15000, 20000, "I am not sure if you have questions."),
        Segment(5, 20000, 25000, "I am not sure if you have questions."),
        Segment(6, 25000, 28000, "I am not sure if you have questions."),
        Segment(7, 28000, 32000, "Real line."),
    ]
    prefix.with_suffix(".srt").write_text(segments_to_srt(original), encoding="utf-8")

    def fake_run(command: list[str]) -> None:
        recovery_prefix = Path(command[command.index("-of") + 1])
        recovery_prefix.with_suffix(".srt").write_text(
            segments_to_srt([Segment(1, 10_000, 13_000, "Actual opening speech.")]),
            encoding="utf-8",
        )

    command = [
        "whisper-cli",
        "-m",
        "/models/ggml-large-v3-turbo-q5_0.bin",
        "-f",
        "speech.wav",
        "-osrt",
        "-of",
        str(prefix),
        "-mc",
        "0",
    ]
    guard._repair_repetition(command, runner=fake_run)

    cleaned = parse_srt(prefix.with_suffix(".srt").read_text(encoding="utf-8"))
    assert [segment.text for segment in cleaned] == ["Actual opening speech.", "Real line."]
    assert (tmp_path / "captions.raw.srt").is_file()
    assert "recovered 1 suspicious region" in guard.quality_note_for(prefix.with_suffix(".srt"))


def test_severe_unrecoverable_loop_is_suppressed_not_passed_downstream(monkeypatch, tmp_path: Path):
    prefix = tmp_path / "captions"
    segments = [Segment(1, 0, 4000, "Good opening.")]
    for index in range(2, 14):
        start = 40_000 + (index - 2) * 4_000
        segments.append(Segment(index, start, start + 4_000, "Same invented sentence."))
    segments.append(Segment(14, 90_000, 94_000, "Good ending."))
    prefix.with_suffix(".srt").write_text(segments_to_srt(segments), encoding="utf-8")

    monkeypatch.setattr(
        guard,
        "_recover_repeat_run",
        lambda command, run, ordinal, *, runner: (None, "still bad"),
    )
    guard._repair_repetition(
        [
            "whisper-cli",
            "-m",
            "/models/ggml-large-v3-turbo-q5_0.bin",
            "-f",
            "speech.wav",
            "-osrt",
            "-of",
            str(prefix),
        ],
        runner=lambda command: None,
    )

    cleaned = parse_srt(prefix.with_suffix(".srt").read_text(encoding="utf-8"))
    assert [segment.text for segment in cleaned] == ["Good opening.", "Good ending."]
    assert "suppressed 12 repeated segment" in guard.quality_note_for(prefix.with_suffix(".srt"))
