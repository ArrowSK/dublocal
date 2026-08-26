from __future__ import annotations

from pathlib import Path

import pytest

import dublocal.updater as updater


def _status(tmp_path: Path, **overrides) -> updater.UpdateStatus:
    values = dict(
        repository=tmp_path,
        branch="main",
        upstream="origin/main",
        local_revision="a" * 40,
        remote_revision="b" * 40,
        ahead=0,
        behind=1,
        dirty=False,
        current_version="0.3.0.dev0",
        checkout_version="0.3.0.dev0",
        remote_version="0.3.1.dev0",
        repair_needed=False,
        dirty_paths=(),
        pending_commits=(),
    )
    values.update(overrides)
    return updater.UpdateStatus(**values)


def test_check_for_updates_reports_remote_commits(monkeypatch, tmp_path: Path):
    responses = {
        ("branch", "--show-current"): "main",
        ("fetch", "--quiet", "origin", "main"): "",
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "origin/main"): "b" * 40,
        ("rev-list", "--left-right", "--count", "HEAD...origin/main"): "0\t3",
        ("status", "--porcelain", "--untracked-files=no"): "",
        ("log", "--format=%h %s", "-n", "8", f"{'a' * 40}..{'b' * 40}"): "abc123 M3 change",
    }

    monkeypatch.setattr(updater, "repository_root", lambda: tmp_path)
    monkeypatch.setattr(updater, "_verify_official_remote", lambda root: None)
    monkeypatch.setattr(updater, "_upstream_ref", lambda root: "origin/main")
    monkeypatch.setattr(
        updater,
        "_run_git",
        lambda root, *args, check=True: responses[tuple(args)],
    )
    monkeypatch.setattr(
        updater,
        "_version_at_revision",
        lambda root, revision: "0.3.0.dev0" if revision.startswith("a") else "0.3.1.dev0",
    )

    status = updater.check_for_updates(fetch_remote=True)

    assert status.update_available is True
    assert status.behind == 3
    assert status.ahead == 0
    assert status.dirty is False
    assert status.remote_version == "0.3.1.dev0"
    assert status.pending_commits == ("abc123 M3 change",)
    assert "3 new commit(s) available" in updater.format_update_status(status)


def test_install_update_refuses_dirty_checkout_and_points_to_repair(monkeypatch, tmp_path: Path):
    status = _status(
        tmp_path,
        dirty=True,
        dirty_paths=(" M src/dublocal/app.py",),
    )
    monkeypatch.setattr(updater, "check_for_updates", lambda fetch_remote=True: status)

    with pytest.raises(updater.UpdateError, match="Repair installation"):
        updater.install_update()


def test_install_update_fast_forwards_and_refreshes_environment(monkeypatch, tmp_path: Path):
    status = _status(tmp_path, behind=2)
    git_calls: list[tuple[str, ...]] = []
    refresh_calls: list[tuple[Path, str]] = []

    monkeypatch.setattr(updater, "check_for_updates", lambda fetch_remote=True: status)

    def fake_git(root, *args, check=True):
        git_calls.append(tuple(args))
        if args == ("rev-parse", "HEAD"):
            return "b" * 40
        return ""

    monkeypatch.setattr(updater, "_run_git", fake_git)
    monkeypatch.setattr(
        updater,
        "_refresh_environment",
        lambda root, version: refresh_calls.append((root, version)),
    )

    result = updater.install_update()

    assert ("merge", "--ff-only", "b" * 40) in git_calls
    assert refresh_calls == [(tmp_path, "0.3.1.dev0")]
    assert result.changed is True
    assert result.restart_required is True
    assert result.repaired is False


def test_install_update_repairs_stale_runtime_without_git_change(monkeypatch, tmp_path: Path):
    revision = "c" * 40
    status = _status(
        tmp_path,
        local_revision=revision,
        remote_revision=revision,
        behind=0,
        current_version="0.2.0.dev0",
        checkout_version="0.3.0.dev0",
        remote_version="0.3.0.dev0",
        repair_needed=True,
    )
    refresh_calls: list[str] = []

    monkeypatch.setattr(updater, "check_for_updates", lambda fetch_remote=True: status)
    monkeypatch.setattr(
        updater,
        "_refresh_environment",
        lambda root, version: refresh_calls.append(version),
    )
    monkeypatch.setattr(updater, "_run_git", lambda root, *args, check=True: revision)

    result = updater.install_update()

    assert refresh_calls == ["0.3.0.dev0"]
    assert result.changed is False
    assert result.repaired is True
    assert result.restart_required is True


def test_repair_dirty_source_requires_explicit_confirmation(monkeypatch, tmp_path: Path):
    status = _status(
        tmp_path,
        dirty=True,
        dirty_paths=(" M src/dublocal/app.py",),
    )
    monkeypatch.setattr(updater, "check_for_updates", lambda fetch_remote=True: status)

    with pytest.raises(updater.UpdateError, match="confirmation"):
        updater.repair_installation(replace_modified_files=False)


def test_repair_dirty_source_backs_up_patch_and_restores_official_files(monkeypatch, tmp_path: Path):
    status = _status(
        tmp_path,
        dirty=True,
        dirty_paths=(" M src/dublocal/app.py",),
    )
    backup = tmp_path / "backup.patch"
    git_calls: list[tuple[str, ...]] = []
    refresh_calls: list[str] = []

    monkeypatch.setattr(updater, "check_for_updates", lambda fetch_remote=True: status)
    monkeypatch.setattr(updater, "_repair_backup", lambda root: backup)
    monkeypatch.setattr(updater, "_version_at_revision", lambda root, revision: "0.3.1.dev0")

    def fake_git(root, *args, check=True):
        git_calls.append(tuple(args))
        if args == ("rev-parse", "HEAD"):
            return "b" * 40
        return ""

    monkeypatch.setattr(updater, "_run_git", fake_git)
    monkeypatch.setattr(
        updater,
        "_refresh_environment",
        lambda root, version: refresh_calls.append(version),
    )

    result = updater.repair_installation(replace_modified_files=True)

    assert ("reset", "--hard", "b" * 40) in git_calls
    assert refresh_calls == ["0.3.1.dev0"]
    assert result.repaired is True
    assert result.source_repaired is True
    assert result.backup_path == backup
    assert result.restart_required is True
