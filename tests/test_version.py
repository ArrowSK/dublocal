from __future__ import annotations

import tomllib
from pathlib import Path

import dublocal


def test_package_version_matches_pyproject():
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    assert dublocal.__version__ == metadata["project"]["version"]


def test_primary_documentation_mentions_current_development_version():
    root = Path(__file__).resolve().parents[1]
    version = dublocal.__version__
    documents = [
        root / "README.md",
        root / "CHANGELOG.md",
        root / "docs" / "INSTALLATION.md",
        root / "docs" / "USER_GUIDE.md",
        root / "docs" / "ARCHITECTURE.md",
        root / "docs" / "TROUBLESHOOTING.md",
    ]

    for document in documents:
        assert version in document.read_text(encoding="utf-8"), document
