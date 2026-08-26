from __future__ import annotations

import os
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
        if dependencies._identity_path(python) == dependencies._identity_path(external):
            return tuple(modules)
        return ()

    monkeypatch.setattr(dependencies, "_probe_python", fake_probe)

    runtime = dependencies.discover_python_runtime(("kokoro",), allow_current=True)

    assert runtime is not None
    assert runtime.python == dependencies._identity_path(external)
    assert runtime.label == "narroam-studio"
    assert runtime.modules == ("kokoro",)


def test_virtualenv_symlink_identity_is_not_collapsed(monkeypatch, tmp_path: Path):
    framework_python = tmp_path / "framework-python"
    framework_python.write_text("", encoding="utf-8")
    framework_python.chmod(0o755)

    current = tmp_path / "dublocal" / ".venv" / "bin" / "python"
    external = tmp_path / "narroam-studio" / ".venv" / "bin" / "python"
    current.parent.mkdir(parents=True)
    external.parent.mkdir(parents=True)
    os.symlink(framework_python, current)
    os.symlink(framework_python, external)

    monkeypatch.setattr(dependencies.sys, "executable", str(current))
    monkeypatch.setattr(
        dependencies,
        "_candidate_pythons",
        lambda: [
            (dependencies._identity_path(current), "DubLocal environment"),
            (dependencies._identity_path(external), "narroam-studio"),
        ],
    )

    def fake_probe(python, modules):
        if dependencies._identity_path(python) == dependencies._identity_path(external):
            return tuple(modules)
        return ()

    monkeypatch.setattr(dependencies, "_probe_python", fake_probe)

    runtime = dependencies.discover_python_runtime(("kokoro",), allow_current=True)

    assert runtime is not None
    assert runtime.python == dependencies._identity_path(external)
    assert runtime.python != dependencies._identity_path(current)


def test_python_from_entrypoint_uses_absolute_shebang(monkeypatch, tmp_path: Path):
    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    command = tmp_path / "bin" / "kokoro"
    command.parent.mkdir(parents=True)
    command.write_text(f"#!{python}\nprint('stub')\n", encoding="utf-8")

    monkeypatch.setattr(dependencies.shutil, "which", lambda name: str(command))

    assert dependencies._python_from_entrypoint("kokoro") == dependencies._identity_path(python)


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
