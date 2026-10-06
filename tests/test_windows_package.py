from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_windows_bootstrap_uses_a_managed_checkout_and_private_venv() -> None:
    script = _text("scripts/windows/beta-bootstrap.ps1")

    assert "https://github.com/ArrowSK/dublocal.git" in script
    assert 'Join-Path $env:LOCALAPPDATA "DubLocal"' in script
    assert "git clone --branch $ExpectedBranch --single-branch" in script
    assert "reset --hard $DubLocalBuildSha" in script
    assert "-m venv $VenvRoot" in script
    assert "pip install --disable-pip-version-check -e $SourceRoot" in script
    assert "dublocal.launcher_runtime" in script
    assert "Start-Process $Url" in script


def test_windows_bootstrap_does_not_bundle_models_or_install_system_software() -> None:
    script = _text("scripts/windows/beta-bootstrap.ps1")

    assert "Model Manager" not in script
    assert "winget install" not in script
    assert "choco install" not in script
    assert "ffmpeg.exe" in script


def test_windows_installer_is_per_user_and_unsigned() -> None:
    installer = _text("packaging/windows/DubLocal.iss")
    builder = _text("scripts/windows/build-beta-installer.ps1")

    assert "PrivilegesRequired=lowest" in installer
    assert "DefaultDirName={localappdata}\\DubLocal Launcher" in installer
    assert "Windows-Setup-unsigned" in installer
    assert "Stop DubLocal" in installer
    assert "Get-FileHash -Algorithm SHA256" in builder
    assert "Inno Setup 6 is required" in builder


def test_windows_workflow_builds_after_the_macos_prerelease() -> None:
    workflow = _text(".github/workflows/beta-windows.yml")

    assert 'workflows: ["macOS Beta Package"]' in workflow
    assert "runs-on: windows-2022" in workflow
    assert "choco install innosetup" in workflow
    assert "build-beta-installer.ps1" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "gh release upload" in workflow
