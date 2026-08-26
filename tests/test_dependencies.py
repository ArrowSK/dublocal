from __future__ import annotations

from pathlib import Path

import dublocal.dependencies as dependencies


def test_discovers_compatible_external_python_runtime(monkeypatch, tmp_path: Path):
    current = tmp_path / "current-python"
    external = tmp_path / "studio" / ".venv" / "bin" / "python"
    external.parent.mkdir(parents=True)
    current.write_text("", encoding="utf-8")
    external.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        dependencies,
        "_candidate_pythons",
        lambda: [(current, "DubLocal environment"), (external, "narroam-studio")],
    )
    monkeypatch.setattr(dependencies.sys, "executable", str(current))

    def fake_probe(python, modules):
        if python.resolve() == external.resolve():
            return tuple(modules)
        return ()

    monkeypatch.setattr(dependencies, "_probe_python", fake_probe)

    runtime = dependencies.discover_python_runtime(("kokoro",), allow_current=True)

    assert runtime is not None
    assert runtime.python == external.resolve()
    assert runtime.label == "narroam-studio"
    assert runtime.modules == ("kokoro",)


def test_python_from_entrypoint_uses_absolute_shebang(monkeypatch, tmp_path: Path):
    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    command = tmp_path / "bin" / "kokoro"
    command.parent.mkdir(parents=True)
    command.write_text(f"#!{python}\nprint('stub')\n", encoding="utf-8")

    monkeypatch.setattr(dependencies.shutil, "which", lambda name: str(command))

    assert dependencies._python_from_entrypoint("kokoro") == python


def test_python_from_entrypoint_ignores_env_shebang(monkeypatch, tmp_path: Path):
    command = tmp_path / "kokoro"
    command.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    monkeypatch.setattr(dependencies.shutil, "which", lambda name: str(command))

    assert dependencies._python_from_entrypoint("kokoro") is None


def test_shared_huggingface_cache_respects_environment(monkeypatch, tmp_path: Path):
    explicit = tmp_path / "shared-hf"
    monkeypatch.setenv("HF_HUB_CACHE", str(explicit))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "ignored-home"))

    assert dependencies.shared_huggingface_cache() == explicit


def test_shared_huggingface_cache_falls_back_to_hf_home(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))

    assert dependencies.shared_huggingface_cache() == tmp_path / "hf-home" / "hub"
