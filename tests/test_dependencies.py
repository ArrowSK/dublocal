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
    monkeypatch.setattr(dependencies.Path, "resolve", lambda self: self)
    monkeypatch.setattr(dependencies.sys, "executable", str(current))

    def fake_probe(python, modules):
        if python == external:
            return tuple(modules)
        return ()

    monkeypatch.setattr(dependencies, "_probe_python", fake_probe)

    runtime = dependencies.discover_python_runtime(("kokoro",), allow_current=True)

    assert runtime is not None
    assert runtime.python == external
    assert runtime.label == "narroam-studio"
    assert runtime.modules == ("kokoro",)


def test_shared_huggingface_cache_respects_environment(monkeypatch, tmp_path: Path):
    explicit = tmp_path / "shared-hf"
    monkeypatch.setenv("HF_HUB_CACHE", str(explicit))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "ignored-home"))

    assert dependencies.shared_huggingface_cache() == explicit


def test_shared_huggingface_cache_falls_back_to_hf_home(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))

    assert dependencies.shared_huggingface_cache() == tmp_path / "hf-home" / "hub"
