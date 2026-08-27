from __future__ import annotations

import json
from pathlib import Path

import dublocal.m52 as m52
import dublocal.transcription as transcription


def test_timing_plan_slows_short_voice_and_ends_near_subtitle_end():
    plan = m52.plan_segment_timing(10_000, 14_000, 2_600)

    assert plan.start_ms > 10_000
    assert plan.tempo_factor < 1.0
    assert plan.exact is True
    assert abs((plan.start_ms + plan.expected_duration_ms) - 14_000) <= 45


def test_timing_plan_speeds_long_voice_to_subtitle_window():
    plan = m52.plan_segment_timing(0, 4_000, 5_200)

    assert plan.start_ms > 0
    assert plan.tempo_factor > 1.0
    assert plan.exact is True
    assert abs((plan.start_ms + plan.expected_duration_ms) - 4_000) <= 45


def test_extreme_timing_change_is_reported_not_overstretched():
    plan = m52.plan_segment_timing(0, 7_000, 400)

    assert plan.tempo_factor == 0.5
    assert plan.exact is False


def test_transcription_uses_vad_when_supported(monkeypatch, tmp_path: Path):
    model = tmp_path / "ggml-base.bin"
    model.write_bytes(b"model")
    vad = tmp_path / "ggml-silero-v6.2.0.bin"
    vad.write_bytes(b"vad")
    source = tmp_path / "source.mkv"
    source.write_bytes(b"media")
    wav = tmp_path / "speech.wav"
    wav.write_bytes(b"wav")
    job = tmp_path / "job"
    job.mkdir()
    captured: list[str] = []

    monkeypatch.setattr(transcription, "find_whisper_cli", lambda: "/usr/local/bin/whisper-cli")
    monkeypatch.setattr(transcription, "whisper_model_path", lambda model_id: model)
    monkeypatch.setattr(transcription, "_new_job_dir", lambda prefix: job)
    monkeypatch.setattr(transcription, "_source_media_path", lambda info, output_dir: source)
    monkeypatch.setattr(transcription, "_convert_to_whisper_wav", lambda source_path, output_dir: wav)
    monkeypatch.setattr(transcription, "_whisper_supports_vad", lambda executable: True)
    monkeypatch.setattr(transcription, "_ensure_whisper_vad_model", lambda: vad)
    monkeypatch.setattr(transcription.platform, "machine", lambda: "arm64")

    def fake_whisper(command):
        captured.extend(command)
        output_prefix = Path(command[command.index("-of") + 1])
        output_prefix.with_suffix(".srt").write_text(
            "1\n00:00:28,000 --> 00:00:31,000\nReal speech.\n",
            encoding="utf-8",
        )
        output_prefix.with_suffix(".json").write_text(
            json.dumps({"result": {"language": "en"}}),
            encoding="utf-8",
        )

    monkeypatch.setattr(transcription, "_run_whisper_with_progress", fake_whisper)

    result = transcription.transcribe_source({"kind": "local", "path": str(source)})

    assert result.vad_used is True
    assert "--vad" in captured
    assert captured[captured.index("--vad-model") + 1] == str(vad)
    assert captured[captured.index("--vad-threshold") + 1] == "0.45"
    assert captured[captured.index("-mc") + 1] == "64"
    assert captured[captured.index("-nth") + 1] == "0.50"
