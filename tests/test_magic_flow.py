from __future__ import annotations

from pathlib import Path

import pytest

import dublocal.magic_flow as magic
from dublocal.media import DubLocalError


def _info(*tracks):
    return {"kind": "youtube", "title": "Example", "subtitle_tracks": list(tracks)}


def test_magic_prefers_creator_subtitles_over_local_asr(monkeypatch):
    monkeypatch.setattr(magic, "_installed_whisper", lambda model_id: True)
    info = _info(
        {"label": "English · manual", "value": "manual:en", "source": "manual", "language": "en"},
        {"label": "English · automatic", "value": "auto:en", "source": "auto", "language": "en"},
    )

    decision = magic.recommend_subtitle_source(info, "auto")

    assert decision.method == "existing"
    assert decision.track_value == "manual:en"
    assert "creator/embedded" in decision.label


def test_magic_prefers_installed_accurate_model_over_automatic_captions(monkeypatch):
    monkeypatch.setattr(
        magic,
        "_installed_whisper",
        lambda model_id: model_id == "large-v3-turbo-q5_0",
    )
    info = _info(
        {"label": "English · automatic", "value": "auto:en", "source": "auto", "language": "en"},
    )

    decision = magic.recommend_subtitle_source(info, "auto")

    assert decision.method == "transcribe"
    assert decision.model_id == "large-v3-turbo-q5_0"


def test_magic_uses_automatic_caption_when_accurate_is_not_installed(monkeypatch):
    monkeypatch.setattr(magic, "_installed_whisper", lambda model_id: False)
    info = _info(
        {"label": "English · automatic", "value": "auto:en", "source": "auto", "language": "en"},
    )

    decision = magic.recommend_subtitle_source(info, "auto")

    assert decision.method == "existing"
    assert decision.track_value == "auto:en"


def test_magic_fails_clearly_when_no_subtitle_route_exists(monkeypatch):
    monkeypatch.setattr(magic, "_installed_whisper", lambda model_id: False)

    with pytest.raises(DubLocalError, match="no local Whisper model"):
        magic.recommend_subtitle_source(_info(), "auto")


def test_magic_force_local_uses_best_installed_model(monkeypatch):
    installed = {"base"}
    monkeypatch.setattr(magic, "_installed_whisper", lambda model_id: model_id in installed)

    decision = magic.recommend_subtitle_source(_info(), "local")

    assert decision.method == "transcribe"
    assert decision.model_id == "base"


def test_magic_force_local_fast_selects_base_even_when_best_is_installed(monkeypatch):
    installed = {"base", "large-v3-turbo-q5_0"}
    monkeypatch.setattr(magic, "_installed_whisper", lambda model_id: model_id in installed)

    decision = magic.recommend_subtitle_source(_info(), "local-fast")

    assert decision.method == "transcribe"
    assert decision.model_id == "base"
    assert "Base" in decision.label


def test_magic_force_local_best_selects_accurate(monkeypatch):
    installed = {"base", "large-v3-turbo-q5_0"}
    monkeypatch.setattr(magic, "_installed_whisper", lambda model_id: model_id in installed)

    decision = magic.recommend_subtitle_source(_info(), "local-best")

    assert decision.method == "transcribe"
    assert decision.model_id == "large-v3-turbo-q5_0"
    assert "Large v3 Turbo" in decision.label


def test_magic_force_local_quality_requires_selected_model(monkeypatch):
    monkeypatch.setattr(magic, "_installed_whisper", lambda model_id: model_id == "base")

    with pytest.raises(DubLocalError, match="BEST local transcription"):
        magic.recommend_subtitle_source(_info(), "local-best")
