from __future__ import annotations

from pathlib import Path

import dublocal.normal_update as normal
from dublocal.updater import UpdateResult, UpdateStatus


def _status(tmp_path: Path, **overrides) -> UpdateStatus:
    values = dict(
        repository=tmp_path,
        branch="main",
        upstream="origin/main",
        local_revision="a" * 40,
        remote_revision="b" * 40,
        ahead=0,
        behind=1,
        dirty=False,
        current_version="0.6.0.dev0",
        checkout_version="0.6.0.dev0",
        remote_version="0.6.1.dev0",
        repair_needed=False,
        dirty_paths=(),
        pending_commits=(),
    )
    values.update(overrides)
    return UpdateStatus(**values)


def test_one_action_update_installs_and_schedules_restart(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(normal, "check_for_updates", lambda fetch_remote=True: _status(tmp_path))
    monkeypatch.setattr(
        normal,
        "install_update",
        lambda: UpdateResult("a" * 40, "b" * 40, True, True),
    )
    restarted: list[bool] = []
    monkeypatch.setattr(normal, "schedule_restart", lambda: restarted.append(True))

    text = normal.update_dublocal_ui()

    assert "restarting automatically" in text
    assert restarted == [True]


def test_one_action_update_reports_up_to_date_without_restart(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        normal,
        "check_for_updates",
        lambda fetch_remote=True: _status(
            tmp_path,
            local_revision="a" * 40,
            remote_revision="a" * 40,
            behind=0,
            remote_version="0.6.0.dev0",
        ),
    )
    monkeypatch.setattr(
        normal,
        "install_update",
        lambda: UpdateResult("a" * 40, "a" * 40, False, False),
    )
    monkeypatch.setattr(
        normal,
        "schedule_restart",
        lambda: (_ for _ in ()).throw(AssertionError("restart should not be scheduled")),
    )

    text = normal.update_dublocal_ui()

    assert "up to date" in text


def test_one_action_update_repairs_dirty_managed_files_with_backup(monkeypatch, tmp_path: Path) -> None:
    backup = tmp_path / "backup.patch"
    monkeypatch.setattr(
        normal,
        "check_for_updates",
        lambda fetch_remote=True: _status(
            tmp_path,
            dirty=True,
            dirty_paths=(" M src/dublocal/app.py",),
        ),
    )
    calls: list[bool] = []

    def repair(*, replace_modified_files=False):
        calls.append(replace_modified_files)
        return UpdateResult(
            "a" * 40,
            "b" * 40,
            True,
            True,
            repaired=True,
            source_repaired=True,
            backup_path=backup,
        )

    monkeypatch.setattr(normal, "repair_installation", repair)
    monkeypatch.setattr(normal, "schedule_restart", lambda: None)

    text = normal.update_dublocal_ui()

    assert calls == [True]
    assert str(backup) in text


def test_one_action_update_never_overwrites_local_commits(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        normal,
        "check_for_updates",
        lambda fetch_remote=True: _status(tmp_path, ahead=2, behind=0),
    )
    monkeypatch.setattr(
        normal,
        "install_update",
        lambda: (_ for _ in ()).throw(AssertionError("must not install")),
    )

    text = normal.update_dublocal_ui()

    assert "2 local commit" in text
    assert "No files were changed" in text
