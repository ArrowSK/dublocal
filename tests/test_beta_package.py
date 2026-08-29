from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_beta_bootstrap_preserves_managed_git_updater_architecture() -> None:
    script = _text("scripts/macos/beta-bootstrap.sh")

    assert "Library/Application Support/DubLocal" in script
    assert "https://github.com/ArrowSK/dublocal.git" in script
    assert 'EXPECTED_BRANCH="main"' in script
    assert 'git clone --branch "$EXPECTED_BRANCH" --single-branch' in script
    assert 'git -C "$SOURCE_ROOT" reset --hard "$BUILD_SHA"' in script
    assert 'pip install --disable-pip-version-check -e "$SOURCE_ROOT"' in script
    assert 'scripts/macos/launch-dublocal.sh' in script
    assert "Model Manager" not in script  # models remain controlled inside the app


def test_beta_builder_creates_branded_unsigned_dmg() -> None:
    script = _text("scripts/macos/build-beta-dmg.sh")

    assert "assets/macos/DubLocal.svg" in script
    assert "/usr/bin/iconutil -c icns" in script
    assert "/usr/bin/osacompile -o" in script
    assert "io.github.arrowsk.dublocal" in script
    assert "CFBundleShortVersionString" in script
    assert "/usr/bin/codesign -dv" in script
    assert "/usr/bin/hdiutil create" in script
    assert "/usr/bin/hdiutil verify" in script
    assert "macOS-unsigned.dmg" in script
    assert "Do not disable Gatekeeper globally" in script


def test_beta_workflow_builds_on_real_macos_runner_and_uploads_dmg() -> None:
    workflow = _text(".github/workflows/beta-macos.yml")

    assert "runs-on: macos-14" in workflow
    assert "zsh scripts/macos/build-beta-dmg.sh" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "dist/*.dmg" in workflow


def test_beta_package_version_matches_python_package() -> None:
    metadata = tomllib.loads(_text("pyproject.toml"))
    version = metadata["project"]["version"]
    init = _text("src/dublocal/__init__.py")

    assert f'__version__ = "{version}"' in init
    assert version in _text("scripts/macos/beta-bootstrap.sh")
