from __future__ import annotations

import json
import os
import time
from pathlib import Path

import dublocal.storage_cleanup as cleanup


def _write(path: Path, size: int = 16) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_clean_temporary_files_never_touches_protected_data(monkeypatch, tmp_path: Path) -> None:
    jobs = tmp_path / "cache" / "jobs"
    translations = tmp_path / "cache" / "translations"
    models = tmp_path / "data" / "models"
    sessions = tmp_path / "config" / "authenticated-web" / "profiles"
    outputs = tmp_path / "Movies" / "DubLocal"

    _write(jobs / "job-a" / "source.mp4", 100)
    _write(translations / "translation.json", 40)
    model = _write(models / "whisper" / "model.bin", 200)
    session = _write(sessions / "domestika" / "Cookies", 80)
    output = _write(outputs / "Course" / "01.dub.en.mkv", 300)

    monkeypatch.setattr(cleanup, "jobs_root", lambda: jobs)
    monkeypatch.setattr(cleanup, "translation_cache_root", lambda: translations)
    monkeypatch.setattr(cleanup, "managed_models_root", lambda: models)
    monkeypatch.setattr(cleanup, "browser_profile_root", lambda: sessions)
    monkeypatch.setattr(cleanup, "finished_output_roots", lambda: (outputs,))
    monkeypatch.setattr(cleanup, "course_manifest_root", lambda: tmp_path / "course-jobs")
    monkeypatch.setattr(cleanup, "repair_backups_root", lambda: tmp_path / "repairs")
    monkeypatch.setattr(cleanup, "_current_playwright_revision", lambda: None)
    monkeypatch.setattr(cleanup, "job_active", lambda: False)

    result = cleanup.clean_temporary_files()

    assert result.removed_bytes >= 140
    assert not any(jobs.iterdir())
    assert not any(translations.iterdir())
    assert model.is_file()
    assert session.is_file()
    assert output.is_file()


def test_clean_temporary_files_refuses_active_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cleanup, "job_active", lambda: True)
    monkeypatch.setattr(cleanup, "jobs_root", lambda: tmp_path / "jobs")
    monkeypatch.setattr(cleanup, "translation_cache_root", lambda: tmp_path / "translations")

    try:
        cleanup.clean_temporary_files()
    except RuntimeError as exc:
        assert "Stop the active DubLocal job" in str(exc)
    else:
        raise AssertionError("cleanup must not run while a job is active")


def test_course_manifest_retention_preserves_unfinished_longer(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "course-jobs"
    root.mkdir()
    now = time.time()

    done = root / "done.json"
    done.write_text(json.dumps({"items": {"1": {"state": "done"}}}), encoding="utf-8")
    os.utime(done, (now - 100 * 86400, now - 100 * 86400))

    unfinished = root / "unfinished.json"
    unfinished.write_text(json.dumps({"items": {"1": {"state": "failed"}}}), encoding="utf-8")
    os.utime(unfinished, (now - 100 * 86400, now - 100 * 86400))

    ancient = root / "ancient.json"
    ancient.write_text(json.dumps({"items": {"1": {"state": "failed"}}}), encoding="utf-8")
    os.utime(ancient, (now - 190 * 86400, now - 190 * 86400))

    monkeypatch.setattr(cleanup, "course_manifest_root", lambda: root)
    result = cleanup.prune_course_manifests(now=now)

    assert result.removed_items == 2
    assert not done.exists()
    assert unfinished.exists()
    assert not ancient.exists()


def test_repair_backups_are_age_and_count_bounded(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repair-backups"
    root.mkdir()
    now = time.time()

    for index in range(12):
        path = _write(root / f"recent-{index:02d}.patch", 10)
        stamp = now - index * 60
        os.utime(path, (stamp, stamp))
    old = _write(root / "old.patch", 10)
    os.utime(old, (now - 45 * 86400, now - 45 * 86400))

    monkeypatch.setattr(cleanup, "repair_backups_root", lambda: root)
    result = cleanup.prune_repair_backups(now=now)

    assert result.removed_items == 3
    remaining = sorted(root.glob("*.patch"))
    assert len(remaining) == cleanup.REPAIR_KEEP
    assert not old.exists()


def test_log_is_rotated_before_new_launch(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "logs"
    root.mkdir()
    current = _write(root / "dublocal.log", cleanup.LOG_ROTATE_BYTES + 1)
    _write(root / "dublocal.log.1", 31)
    _write(root / "dublocal.log.2", 32)
    _write(root / "dublocal.log.3", 33)

    monkeypatch.setattr(cleanup, "logs_root", lambda: root)
    result = cleanup.prepare_log_for_launch()

    assert result.removed_items == 1
    assert not current.exists()
    assert (root / "dublocal.log.1").stat().st_size == cleanup.LOG_ROTATE_BYTES + 1
    assert (root / "dublocal.log.2").stat().st_size == 31
    assert (root / "dublocal.log.3").stat().st_size == 32


def test_old_playwright_revision_pruning_keeps_current(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "ms-playwright"
    current = _write(root / "chromium-1200" / "chrome", 20)
    current_headless = _write(root / "chromium_headless_shell-1200" / "shell", 20)
    old = _write(root / "chromium-1100" / "chrome", 40)
    old_headless = _write(root / "chromium_headless_shell-1100" / "shell", 40)
    now = time.time()
    for path in (old.parent, old_headless.parent):
        os.utime(path, (now - 60 * 86400, now - 60 * 86400))

    monkeypatch.setattr(cleanup, "_current_playwright_revision", lambda: (root, "1200"))
    result = cleanup.prune_old_playwright_revisions(now=now)

    assert result.removed_items == 2
    assert current.is_file()
    assert current_headless.is_file()
    assert not old.parent.exists()
    assert not old_headless.parent.exists()
