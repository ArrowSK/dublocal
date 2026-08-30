from __future__ import annotations

import tomllib
from pathlib import Path

import dublocal


def test_package_version_matches_pyproject():
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    assert dublocal.__version__ == metadata["project"]["version"]


def test_versioned_public_surfaces_match_current_beta():
    root = Path(__file__).resolve().parents[1]
    version = dublocal.__version__
    documents = [
        root / "README.md",
        root / "CHANGELOG.md",
        root / "docs" / "BETA_INSTALLATION.md",
        root / f"docs/RELEASE_NOTES_{version}.md",
    ]

    for document in documents:
        assert document.is_file(), document
        assert version in document.read_text(encoding="utf-8"), document
