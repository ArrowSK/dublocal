from __future__ import annotations

import json
from pathlib import Path

import pytest

from dublocal import tts
from dublocal.media import DubLocalError
from dublocal.tts_provider_registry import (
    BUILTIN_RUSSIAN_PROVIDER,
    TTSProvider,
    provider_for_language,
    register_custom_provider,
    validate_provider_manifest,
)
from dublocal.tts_provider_worker import _fit_speed
import dublocal.tts_provider_registry as registry
import dublocal.tts_provider_refinement as refinement


def _local_manifest(path: Path, *, provider_id: str = "test-russian", preferred: bool = True) -> dict:
    return {
        "schema_version": 1,
        "id": provider_id,
        "label": "Test Russian provider",
        "language": "ru",
        "language_label": "Russian",
        "backend": "kokoro-local",
        "frontend": "russian-v2",
        "source": {"type": "local", "path": str(path)},
        "license": {
            "id": "Test-License",
            "commercial_use": True,
            "redistribution": "not-bundled",
            "source": "test",
            "attribution": "test",
        },
        "config_file": "kokoro-config.json",
        "voices": [
            {
                "id": "rf_test",
                "label": "Test · female",
                "gender": "female",
                "model_file": "model.pth",
                "voice_file": "voices/test.pt",
            }
        ],
        "default_voice": "rf_test",
        "preferred": preferred,
    }


def _snapshot_tts_metadata() -> tuple[dict, list, dict, dict]:
    return (
        dict(tts.KOKORO_LANGUAGES),
        list(tts.KOKORO_LANGUAGE_CHOICES),
        dict(tts._PREPARE_TEXT),
        dict(tts._TRANSLATION_TO_KOKORO),
    )


def _restore_tts_metadata(snapshot: tuple[dict, list, dict, dict]) -> None:
    languages, choices, prepare_text, translation_map = snapshot
    tts.KOKORO_LANGUAGES.clear()
    tts.KOKORO_LANGUAGES.update(languages)
    tts.KOKORO_LANGUAGE_CHOICES[:] = choices
    tts._PREPARE_TEXT.clear()
    tts._PREPARE_TEXT.update(prepare_text)
    tts._TRANSLATION_TO_KOKORO.clear()
    tts._TRANSLATION_TO_KOKORO.update(translation_map)


def test_builtin_russian_provider_is_pinned_and_commercially_declared() -> None:
    provider = validate_provider_manifest(BUILTIN_RUSSIAN_PROVIDER, builtin=True)
    assert provider["language"] == "ru"
    assert provider["source"]["repo_id"] == "zaakirio/kokoro-ru"
    assert provider["source"]["revision"] != "main"
    assert provider["license"]["commercial_use"] is True
    assert provider["checksums"]["kokoro-ru-v2-base.pth"] == (
        "3bbee5bc05cfa182afc365b9116eaed8355f939c3c0af8aa0e43fdc45343ca15"
    )
    assert [voice["id"] for voice in provider["voices"]] == ["rf_sveta", "rf_masha", "rm_dima"]


def test_custom_provider_rejects_executable_plugin_fields(tmp_path: Path) -> None:
    raw = _local_manifest(tmp_path)
    raw["command"] = "python evil.py"
    with pytest.raises(DubLocalError, match="data-only"):
        validate_provider_manifest(raw)


def test_remote_provider_rejects_mutable_revision(tmp_path: Path) -> None:
    raw = _local_manifest(tmp_path)
    raw["source"] = {
        "type": "huggingface",
        "repo_id": "example/model",
        "revision": "main",
    }
    with pytest.raises(DubLocalError, match="immutable"):
        validate_provider_manifest(raw)


def test_remote_custom_provider_requires_primary_asset_checksums(tmp_path: Path) -> None:
    raw = _local_manifest(tmp_path)
    raw["source"] = {
        "type": "huggingface",
        "repo_id": "example/model",
        "revision": "0123456789abcdef",
    }
    with pytest.raises(DubLocalError, match="SHA-256 pin every"):
        validate_provider_manifest(raw)


def test_local_custom_provider_can_be_registered_without_executable_code(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setattr(registry, "provider_config_root", lambda: config)

    provider = register_custom_provider(json.dumps(_local_manifest(source)))
    written = json.loads((config / f"{provider.id}.json").read_text(encoding="utf-8"))
    assert written["backend"] == "kokoro-local"
    assert "builtin" not in written
    assert "command" not in written


def test_installed_preferred_custom_provider_can_replace_builtin(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    config = tmp_path / "config"
    install = tmp_path / "install"
    config.mkdir()
    install.mkdir()
    monkeypatch.setattr(registry, "provider_config_root", lambda: config)
    monkeypatch.setattr(registry, "provider_install_root", lambda: install)

    custom = TTSProvider(validate_provider_manifest(_local_manifest(source)))
    (config / f"{custom.id}.json").write_text(
        json.dumps(custom.manifest), encoding="utf-8"
    )
    custom_dir = install / custom.id
    custom_dir.mkdir()
    required = ["kokoro-config.json"]
    (custom_dir / "kokoro-config.json").write_text("{}", encoding="utf-8")
    (custom_dir / "install-receipt.json").write_text(
        json.dumps({"provider_id": custom.id, "required_files": required}), encoding="utf-8"
    )

    selected = provider_for_language("ru", require_installed=True)
    assert selected is not None
    assert selected.id == custom.id


def test_provider_timing_never_slows_a_line_that_fits() -> None:
    assert _fit_speed(1.0, 3000, 5000) == 1.0
    assert _fit_speed(0.8, 3000, 5000) == 0.8
    assert 1.6 < _fit_speed(1.0, 5000, 3000) < 1.7


def test_russian_is_exposed_through_language_to_provider_mapping(monkeypatch) -> None:
    snapshot = _snapshot_tts_metadata()
    try:
        monkeypatch.setattr(refinement, "all_providers", registry.all_providers)
        refinement._apply_provider_metadata()
        assert tts.suggested_kokoro_language("ru") == "ru"
        assert tts.kokoro_default_voice("ru") == "rf_sveta"
        choices = dict((value, label) for label, value in tts.kokoro_voice_choices("ru"))
        assert "rf_sveta" in choices
        assert "rm_dima" in choices
    finally:
        _restore_tts_metadata(snapshot)
