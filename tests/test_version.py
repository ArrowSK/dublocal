from __future__ import annotations

import tomllib
from pathlib import Path

import dublocal


def test_package_version_matches_pyproject():
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    assert dublocal.__version__ == metadata["project"]["version"]
