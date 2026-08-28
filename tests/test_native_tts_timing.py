from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import dublocal.kokoro_worker as worker
import dublocal.native_tts_timing as native


def _write_srt(path: Path) -> None:
    path.write_text(
        "1\n00:00:01,000 --> 00:00:05,000\nHello there.\n\n"
        "2\n00:00:06,000 --> 00:00:08,500\nSecond line.\n",
        encoding="utf-8",
    )


def test_native_speed_estimate_only_speeds_up_overflow_by_default():
    assert worker._native_speed_for_target(1.0, 3_000, 4_000) == 1.0
    assert worker._native_speed_for_target(1.0, 4_000, 2_000) == 2.0
    assert worker._native_speed_for_target(1.0, 1_000, 4_000) == 1.0
    assert worker._native_speed_for_target(0.8, 1_000, 4_000) == 0.8
    assert worker._native_speed_for_target(
        1.0,
        3_000,
        4_000,
        allow_slowdown=True,
    ) == 0.75


def test_worker_request_receives_per_segment_subtitle_targets():
    request = {
        "speed": 1.0,
        "segments": [
            {"index": 1, "text": "Hello", "voice": "am_adam"},
            {"index": 2, "text": "Again", "voice": "af_heart"},
        ],
    }
    enriched = native._apply_timing_targets(request, {1: 4_000, 2: 2_500})

    assert enriched["adaptive_timing"] is True
    assert enriched["segments"][0]["target_duration_ms"] == 4_000
    assert enriched["segments"][1]["target_duration_ms"] == 2_500
    assert enriched["segments"][0]["voice"] == "am_adam"
    assert enriched["segments"][1]["voice"] == "af_heart"
    assert "target_duration_ms" not in request["segments"][0]


def test_generation_wrapper_enriches_worker_and_manifest(monkeypatch, tmp_path: Path):
    srt = tmp_path / "captions.srt"
    _write_srt(srt)
    manifest = tmp_path / "voice-manifest.json"
    seen = {}

    def fake_worker(request, job_dir):
        seen["request"] = request
        return {
            "segments": [
                {
                    "index": 1,
                    "speed": 1.0,
                    "pilot_duration_ms": 3000,
                    "target_duration_ms": 4000,
                    "timing_error_ms": -1000,
                    "generation_passes": 1,
                },
                {
                    "index": 2,
                    "speed": 1.10,
                    "pilot_duration_ms": 2700,
                    "target_duration_ms": 2500,
                    "timing_error_ms": -30,
                    "generation_passes": 2,
                },
            ]
        }

    def fake_generate(
        subtitle_path,
        *,
        language,
        voice,
        speed=1.0,
        segment_voices=None,
    ):
        native.tts._run_worker(
            {
                "speed": speed,
                "segments": [
                    {
                        "index": 1,
                        "text": "Hello there.",
                        "voice": (segment_voices or {}).get(1, voice),
                    },
                    {
                        "index": 2,
                        "text": "Second line.",
                        "voice": (segment_voices or {}).get(2, voice),
                    },
                ],
            },
            tmp_path,
        )
        manifest.write_text(
            json.dumps(
                {
                    "speed": speed,
                    "segments": [
                        {"index": 1, "slot_ms": 4000},
                        {"index": 2, "slot_ms": 2500},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(manifest_path=manifest)

    monkeypatch.setattr(native, "_ORIGINAL_RUN_WORKER", fake_worker)
    monkeypatch.setattr(native, "_ORIGINAL_GENERATE", fake_generate)

    native.generate_voice_track_native_timed(
        srt,
        language="en-US",
        voice="am_adam",
        speed=1.0,
        segment_voices={2: "af_heart"},
    )

    assert seen["request"]["adaptive_timing"] is True
    assert seen["request"]["segments"][0]["target_duration_ms"] == 4000
    assert seen["request"]["segments"][1]["target_duration_ms"] == 2500
    assert seen["request"]["segments"][1]["voice"] == "af_heart"

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["timing_mode"] == "native_kokoro_speed"
    assert payload["post_stretch"] is False
    assert payload["segments"][0]["native_speed"] == 1.0
    assert payload["segments"][0]["generation_passes"] == 1


def test_export_timing_uses_generated_track_without_waveform_stretch(tmp_path: Path):
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"voice")
    manifest = tmp_path / "voice-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "speed": 1.0,
                "timing_mode": "native_kokoro_speed",
                "segments": [
                    {
                        "index": 1,
                        "slot_ms": 4000,
                        "target_duration_ms": 4000,
                        "native_speed": 1.0,
                        "timing_error_ms": -1000,
                        "generation_passes": 1,
                    },
                    {
                        "index": 2,
                        "slot_ms": 2500,
                        "target_duration_ms": 2500,
                        "native_speed": 1.2,
                        "timing_error_ms": 250,
                        "generation_passes": 2,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = native.use_native_generated_timing(voice, tmp_path / "unused")

    assert result.wav_path == voice.resolve()
    assert result.adjusted_segments == 1
    assert result.remaining_overflows == 1
    assert result.maximum_speedup == 1.2
