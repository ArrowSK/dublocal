from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir

DEFAULT_MAX_AGE_HOURS = 24
DEFAULT_MAX_BYTES = 4 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CachePruneResult:
    removed_items: int
    removed_bytes: int
    remaining_bytes: int


def jobs_root() -> Path:
    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path_size(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file() and not child.is_symlink():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def prune_job_cache(
    *,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    now: float | None = None,
) -> CachePruneResult:
    """Prune generated/intermediate jobs without touching models or shared caches.

    The launcher calls this at startup, so no active DubLocal job is being deleted.
    Files remain available during the current session and for up to the configured age.
    """

    root = jobs_root()
    current = time.time() if now is None else float(now)
    cutoff = current - max(0, int(max_age_hours)) * 3600

    entries: list[tuple[Path, float, int]] = []
    for path in root.iterdir():
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        entries.append((path, modified, _path_size(path)))

    removed_items = 0
    removed_bytes = 0
    kept: list[tuple[Path, float, int]] = []

    for path, modified, size in entries:
        if modified < cutoff:
            _remove(path)
            removed_items += 1
            removed_bytes += size
        else:
            kept.append((path, modified, size))

    remaining = sum(size for _path, _modified, size in kept)
    if max_bytes >= 0 and remaining > max_bytes:
        for path, _modified, size in sorted(kept, key=lambda item: item[1]):
            if remaining <= max_bytes:
                break
            _remove(path)
            removed_items += 1
            removed_bytes += size
            remaining -= size

    return CachePruneResult(
        removed_items=removed_items,
        removed_bytes=removed_bytes,
        remaining_bytes=max(0, remaining),
    )
