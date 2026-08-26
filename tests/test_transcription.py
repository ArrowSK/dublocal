from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import dublocal.transcription as transcription


def test_model_paths_live_outside_repository(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(transcription, "user_data_dir", lambda app: str(tmp_path / "app-data"))

    path = transcription.whisper_model_path("base")

    assert path == tmp_path / "app-data" / "models" / "whisper" / "ggml-base.bin"


def test_transcribe_source_produces_normalized_segments(monkeypatch, tmp_path: Path):
    model = tmp_path / "ggml-base.bin"
    model.write_bytes(b"model")
    source = tmp_path / "source.mkv"
    source.write_bytes(b"media")
    wav = tmp_path / "speech.wav"
    wav.write_bytes(b"wav")
    job = tmp_path / "job"
    job.mkdir()

    monkeypatch.setattr(transcription, "find_whisper_cli", lambda: "/usr/local/bin/whisper-cli")
    monkeypatch.setattr(transcription, "whisper_model_path", lambda model_id: model)
    monkeypatch.setattr(transcription, "_new_job_dir", lambda prefix: job)
    monkeypatch.setattr(transcription, "_source_media_path", lambda info, output_dir: source)
    monkeypatch.setattr(transcription, "_convert_to_whisper_wav", lambda source_path, output_dir: wav)
    monkeypatch.setattr(transcription.platform, "machine", lambda: "arm64")

    def fake_run(command, **kwargs):
        assert "-osrt" in command
        assert "-oj" in command
        assert command[command.index("-l") + 1] == "auto"
        output_prefix = Path(command[command.index("-of") + 1])
        output_prefix.with_suffix(".srt").write_text(
            "1\n00:00:00,500 --> 00:00:02,000\nHello from Whisper.\n",
            encoding="utf-8",
        )
        output_prefix.with_suffix(".json").write_text(
            json.dumps({"result": {"language": "en"}}),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(transcription.subprocess, "run", fake_run)

    result = transcription.transcribe_source({"kind": "local", "path": str(source)})

    assert result.srt_path.name == "captions.srt"
    assert result.model_id == "base"
    assert result.language == "en"
    assert len(result.segments) == 1
    assert result.segments[0].start_ms == 500
    assert result.segments[0].end_ms == 2000
    assert result.segments[0].text == "Hello from Whisper."


def test_intel_transcription_forces_cpu_mode(monkeypatch, tmp_path: Path):
    model = tmp_path / "ggml-tiny.bin"
    model.write_bytes(b"model")
    wav = tmp_path / "speech.wav"
    wav.write_bytes(b"wav")
    source = tmp_path / "source.m4a"
    source.write_bytes(b"media")
    job = tmp_path / "job"
    job.mkdir()
    captured: list[str] = []

    monkeypatch.setattr(transcription, "find_whisper_cli", lambda: "/usr/local/bin/whisper-cli")
    monkeypatch.setattr(transcription, "whisper_model_path", lambda model_id: model)
    monkeypatch.setattr(transcription, "_new_job_dir", lambda prefix: job)
    monkeypatch.setattr(transcription, "_source_media_path", lambda info, output_dir: source)
    monkeypatch.setattr(transcription, "_convert_to_whisper_wav", lambda source_path, output_dir: wav)
    monkeypatch.setattr(transcription.platform, "machine", lambda: "x86_64")

    def fake_run(command, **kwargs):
        captured.extend(command)
        output_prefix = Path(command[command.index("-of") + 1])
        output_prefix.with_suffix(".srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nTest.\n",
            encoding="utf-8",
        )
        output_prefix.with_suffix(".json").write_text(
            json.dumps({"result": {"language": "en"}}),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(transcription.subprocess, "run", fake_run)

    transcription.transcribe_source({"kind": "local", "path": str(source)}, model_id="tiny")

    assert "-ng" in captured
    assert "-oj" in captured
