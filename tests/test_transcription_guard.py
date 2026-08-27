from __future__ import annotations

from pathlib import Path

import dublocal.transcription as transcription
import dublocal.transcription_guard as guard


def test_vad_run_retries_same_job_without_vad_when_no_srt(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []
    output_prefix = tmp_path / "captions"

    def fake_run(command: list[str]) -> None:
        calls.append(list(command))
        if "--vad" not in command:
            output_prefix.with_suffix(".srt").write_text(
                "1\n00:00:28,000 --> 00:00:30,000\nHello.\n",
                encoding="utf-8",
            )

    monkeypatch.setattr(guard, "_ORIGINAL_RUN", fake_run)

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
    guard._run_with_vad_fallback(command)

    assert len(calls) == 2
    assert "--vad" in calls[0]
    assert "--vad" not in calls[1]
    assert "--vad-model" not in calls[1]
    assert output_prefix.with_suffix(".srt").is_file()


def test_accurate_music_profile_does_not_force_vad(monkeypatch):
    observed: list[bool] = []

    monkeypatch.setattr(transcription, "_whisper_supports_vad", lambda _exe: True)

    def fake_transcribe(info, model_id="base", language="auto"):
        observed.append(transcription._whisper_supports_vad("whisper-cli"))
        return object()

    monkeypatch.setattr(guard, "_ORIGINAL_TRANSCRIBE", fake_transcribe)

    guard._transcribe_with_media_policy(
        {"kind": "local", "path": "/tmp/source.mkv"},
        model_id="large-v3-turbo-q5_0",
        language="auto",
    )

    assert observed == [False]
    assert transcription._whisper_supports_vad("whisper-cli") is True


def test_base_profile_keeps_vad_policy(monkeypatch):
    observed: list[bool] = []
    monkeypatch.setattr(transcription, "_whisper_supports_vad", lambda _exe: True)

    def fake_transcribe(info, model_id="base", language="auto"):
        observed.append(transcription._whisper_supports_vad("whisper-cli"))
        return object()

    monkeypatch.setattr(guard, "_ORIGINAL_TRANSCRIBE", fake_transcribe)
    guard._transcribe_with_media_policy({}, model_id="base", language="auto")

    assert observed == [True]
