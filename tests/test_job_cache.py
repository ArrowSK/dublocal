from __future__ import annotations

import os
from pathlib import Path

import dublocal.job_cache as job_cache


def test_prunes_old_job_directories_only(monkeypatch, tmp_path: Path):
    root = tmp_path / "jobs"
    root.mkdir()
    monkeypatch.setattr(job_cache, "jobs_root", lambda: root)

    old = root / "old-job"
    old.mkdir()
    (old / "source.wav").write_bytes(b"x" * 100)
    fresh = root / "fresh-job"
    fresh.mkdir()
    (fresh / "captions.srt").write_text("ok", encoding="utf-8")

    now = 2_000_000.0
    os.utime(old, (now - 48 * 3600, now - 48 * 3600))
    os.utime(fresh, (now - 60, now - 60))

    result = job_cache.prune_job_cache(max_age_hours=24, max_bytes=10_000, now=now)

    assert not old.exists()
    assert fresh.exists()
    assert result.removed_items == 1
    assert result.removed_bytes >= 100


def test_prunes_oldest_recent_jobs_when_cache_exceeds_cap(monkeypatch, tmp_path: Path):
    root = tmp_path / "jobs"
    root.mkdir()
    monkeypatch.setattr(job_cache, "jobs_root", lambda: root)

    first = root / "first"
    second = root / "second"
    first.mkdir()
    second.mkdir()
    (first / "a.bin").write_bytes(b"a" * 80)
    (second / "b.bin").write_bytes(b"b" * 80)

    now = 3_000_000.0
    os.utime(first, (now - 200, now - 200))
    os.utime(second, (now - 100, now - 100))

    result = job_cache.prune_job_cache(max_age_hours=24, max_bytes=100, now=now)

    assert not first.exists()
    assert second.exists()
    assert result.remaining_bytes <= 100
