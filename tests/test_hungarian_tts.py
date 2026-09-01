from __future__ import annotations

import json
import wave
from pathlib import Path
from types import SimpleNamespace

import dublocal.hungarian_tts as hungarian
import dublocal.tts as tts


def _write_wav(path: Path, duration_ms: int, rate: int = 22_050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(round(duration_ms * rate / 1000)))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_non_macos_hungarian_uses_piper_only(monkeypatch):
    monkeypatch.setattr(hungarian.sys, "platform", "win32")

    assert hungarian.macos_hungarian_voices() == []
    assert hungarian.hungarian_default_voice() == "uf_anna"
    assert [value for _label, value in hungarian.hungarian_voice_choices()] == [
        "uf_anna",
        "uf_berta",
        "um_imre",
    ]


def test_macos_hungarian_prefers_installed_system_voice(monkeypatch):
    monkeypatch.setattr(hungarian.sys, "platform", "darwin")
    monkeypatch.setattr(hungarian.shutil, "which", lambda name: "/usr/bin/say" if name == "say" else None)
    monkeypatch.setattr(
        hungarian.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="Tünde                 hu_HU    # Üdvözlöm!\nDaniel                en_US    # Hello!\n",
            stderr="",
        ),
    )

    voices = hungarian.macos_hungarian_voices()
    assert len(voices) == 1
    assert voices[0].name == "Tünde"
    assert voices[0].voice_id.startswith("hu_macos_")
    assert hungarian.hungarian_default_voice() == voices[0].voice_id
    assert hungarian.hungarian_voice_choices()[0][1] == voices[0].voice_id


def test_hungarian_metadata_enables_translation_to_voice_mapping(monkeypatch):
    monkeypatch.setattr(hungarian.sys, "platform", "win32")
    original_languages = dict(tts.KOKORO_LANGUAGES)
    original_choices = list(tts.KOKORO_LANGUAGE_CHOICES)
    original_prepare = dict(tts._PREPARE_TEXT)
    original_mapping = dict(tts._TRANSLATION_TO_KOKORO)
    try:
        hungarian.install_hungarian_metadata()
        assert tts._TRANSLATION_TO_KOKORO["hu"] == "hu"
        assert tts.suggested_kokoro_language("hu-HU") == "hu"
        assert tts.kokoro_default_voice("hu") == "uf_anna"
        assert [value for _label, value in tts.kokoro_voice_choices("hu")] == [
            "uf_anna",
            "uf_berta",
            "um_imre",
        ]
    finally:
        tts.KOKORO_LANGUAGES.clear()
        tts.KOKORO_LANGUAGES.update(original_languages)
        tts.KOKORO_LANGUAGE_CHOICES[:] = original_choices
        tts._PREPARE_TEXT.clear()
        tts._PREPARE_TEXT.update(original_prepare)
        tts._TRANSLATION_TO_KOKORO.clear()
        tts._TRANSLATION_TO_KOKORO.update(original_mapping)


def test_prepare_piper_is_explicit_and_cross_platform(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(hungarian.sys, "platform", "win32")
    runtime = tmp_path / "Scripts" / "python.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(hungarian, "_prepare_piper_runtime", lambda: runtime)
    monkeypatch.setattr(
        hungarian,
        "_prepare_piper_voice",
        lambda voice_id: (calls.append(voice_id) or (tmp_path / "voice.onnx", tmp_path / "voice.json")),
    )

    status = hungarian.prepare_hungarian_tts("uf_anna")

    assert calls == ["uf_anna"]
    assert "Piper" in status
    assert str(runtime) in status


def test_hungarian_generation_keeps_timing_and_regenerates_only_overflow(monkeypatch, tmp_path: Path):
    subtitle = tmp_path / "hungarian.srt"
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nEz egy próba.\n\n"
        "2\n00:00:01,100 --> 00:00:03,100\nRendben.\n",
        encoding="utf-8",
    )
    job = tmp_path / "job"
    monkeypatch.setattr(tts, "_new_job_dir", lambda _prefix: job)
    monkeypatch.setattr(hungarian, "_piper_runtime_ready", lambda: True)
    monkeypatch.setattr(hungarian, "_voice_ready", lambda _spec: True)

    calls: list[tuple[str, float]] = []

    def fake_synthesize(text: str, voice_id: str, speed: float, output: Path) -> str:
        calls.append((text, speed))
        if text.startswith("Ez") and speed <= 1.01:
            duration = 1800
        elif text.startswith("Ez"):
            duration = 950
        else:
            duration = 900
        _write_wav(output, duration)
        return f"Piper · {voice_id}"

    monkeypatch.setattr(hungarian, "_synthesize_once", fake_synthesize)

    result = hungarian.generate_hungarian_voice_track(
        subtitle,
        voice="uf_anna",
        speed=1.0,
    )

    assert result.wav_path.is_file()
    assert len(result.segments) == 2
    assert len(calls) == 3
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["language"] == "hu"
    assert manifest["timing_mode"] == "native_provider_speed"
    assert manifest["segments"][0]["generation_passes"] == 2
    assert manifest["segments"][1]["generation_passes"] == 1
    assert manifest["segments"][0]["start_ms"] == 0
    assert manifest["segments"][1]["start_ms"] == 1100


def test_runtime_python_uses_windows_and_posix_layout(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(hungarian.os, "name", "nt")
    assert hungarian._runtime_python(tmp_path) == tmp_path / "Scripts" / "python.exe"
    monkeypatch.setattr(hungarian.os, "name", "posix")
    assert hungarian._runtime_python(tmp_path) == tmp_path / "bin" / "python"
