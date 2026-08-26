from __future__ import annotations

from pathlib import Path

import dublocal.launcher_runtime as launcher_runtime


def test_gradio_allowed_paths_only_exposes_job_outputs(monkeypatch, tmp_path: Path):
    cache_root = tmp_path / "DubLocal-cache"
    monkeypatch.setattr(launcher_runtime, "user_cache_dir", lambda app: str(cache_root))

    paths = launcher_runtime._gradio_allowed_paths()

    expected = (cache_root / "jobs").resolve()
    assert paths == [str(expected)]
    assert expected.is_dir()
