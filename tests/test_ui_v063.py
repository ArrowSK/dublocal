from __future__ import annotations

from pathlib import Path

import dublocal.ui_v063 as ui


def test_v063_ui_builds_with_batch_magic_and_single_updater() -> None:
    demo = ui.build_app()
    assert demo is not None


def test_force_local_quality_defaults_to_best_when_accurate_is_installed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    accurate = tmp_path / "accurate.bin"
    accurate.write_bytes(b"model")
    monkeypatch.setattr(ui, "whisper_model_path", lambda _model_id: accurate)

    assert ui._default_local_transcription_policy() == "local-best"


def test_force_local_quality_defaults_to_fast_when_accurate_is_not_installed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.bin"
    monkeypatch.setattr(ui, "whisper_model_path", lambda _model_id: missing)

    assert ui._default_local_transcription_policy() == "local-fast"
