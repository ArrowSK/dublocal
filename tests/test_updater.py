from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import dublocal.updater as updater


def test_check_for_updates_reports_remote_commits(monkeypatch, tmp_path: Path):
    responses = {
        ("branch", "--show-current"): "main",
        ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"): "origin/main",
        ("fetch", "--quiet", "origin"): "",
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "origin/main"): "b" * 40,
        ("rev-list", "--left-right", "--count", "HEAD...origin/main"): "0\t3",
        ("status", "--porcelain"): "",
    }

    monkeypatch.setattr(updater, "repository_root", lambda: tmp_path)
    monkeypatch.setattr(
        updater,
        "_run_git",
        lambda root, *args, check=True: responses[tuple(args)],
    )

    status = updater.check_for_updates(fetch_remote=True)

    assert status.update_available is True
    assert status.behind == 3
    assert status.ahead == 0
    assert status.dirty is False
    assert "3 new commit(s) available" in updater.format_update_status(status)


def test_install_update_refuses_dirty_checkout(monkeypatch, tmp_path: Path):
    status = updater.UpdateStatus(
        repository=tmp_path,
        branch="main",
        upstream="origin/main",
        local_revision="a" * 40,
        remote_revision="b" * 40,
        ahead=0,
        behind=1,
        dirty=True,
    )
    monkeypatch.setattr(updater, "check_for_updates", lambda fetch_remote=True: status)

    with pytest.raises(updater.UpdateError, match="local changes"):
        updater.install_update()


def test_install_update_fast_forwards_and_refreshes_environment(monkeypatch, tmp_path: Path):
    status = updater.UpdateStatus(
        repository=tmp_path,
        branch="main",
        upstream="origin/main",
        local_revision="a" * 40,
        remote_revision="b" * 40,
        ahead=0,
        behind=2,
        dirty=False,
    )
    git_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(updater, "check_for_updates", lambda fetch_remote=True: status)

    def fake_git(root, *args, check=True):
        git_calls.append(tuple(args))
        if args == ("rev-parse", "HEAD"):
            return "b" * 40
        return ""

    pip_calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        pip_calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(updater, "_run_git", fake_git)
    monkeypatch.setattr(updater.subprocess, "run", fake_run)

    result = updater.install_update()

    assert ("merge", "--ff-only", "origin/main") in git_calls
    assert pip_calls
    assert pip_calls[0][1:4] == ["-m", "pip", "install"]
    assert result.changed is True
    assert result.restart_required is True
