from __future__ import annotations

from pathlib import Path

from dublocal.dependencies import PythonRuntime
from dublocal import tts_runtime_compat as compat


def test_python313_app_selects_python312_for_kokoro(monkeypatch, tmp_path: Path) -> None:
    current = tmp_path / "python3.13"
    py312 = tmp_path / "python3.12"
    current.write_text("", encoding="utf-8")
    py312.write_text("", encoding="utf-8")

    monkeypatch.setattr(compat.sys, "version_info", (3, 13, 0))
    monkeypatch.setattr(compat.sys, "executable", str(current))
    monkeypatch.setattr(
        compat.shutil,
        "which",
        lambda name: str(py312) if name == "python3.12" else None,
    )
    monkeypatch.setattr(
        compat,
        "_supported_python",
        lambda path: Path(path) == py312,
    )

    assert compat._base_python_candidates() == [py312]


def test_dedicated_runtime_must_use_python_below_313(monkeypatch, tmp_path: Path) -> None:
    python = tmp_path / "python"
    python.write_text("", encoding="utf-8")

    monkeypatch.setattr(compat, "_probe_python_version", lambda _path: (3, 12))
    assert compat._supported_python(python) is True

    monkeypatch.setattr(compat, "_probe_python_version", lambda _path: (3, 13))
    assert compat._supported_python(python) is False


def test_russian_runtime_prefers_dedicated_compatible_environment(monkeypatch, tmp_path: Path) -> None:
    python = tmp_path / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    expected = PythonRuntime(
        python=python,
        label="DubLocal Russian TTS runtime",
        modules=compat._RUSSIAN_MODULES,
    )

    monkeypatch.setattr(compat, "_runtime_python", lambda: python)
    monkeypatch.setattr(compat, "_runtime_from_python", lambda _python, _label: expected)
    monkeypatch.setattr(
        compat,
        "discover_python_runtime",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not probe other runtimes")),
    )

    assert compat.russian_runtime() == expected
