from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir

from .dependencies import shared_huggingface_cache
from .job_cache import DEFAULT_MAX_AGE_HOURS, DEFAULT_MAX_BYTES, jobs_root, prune_job_cache
from .job_control import job_active
from .translation_cache import prune_translation_cache, translation_cache_root


LOG_ROTATE_BYTES = 5 * 1024 * 1024
LOG_KEEP = 3
COURSE_DONE_RETENTION_DAYS = 90
COURSE_UNFINISHED_RETENTION_DAYS = 180
REPAIR_RETENTION_DAYS = 30
REPAIR_KEEP = 10
PLAYWRIGHT_OLD_REVISION_DAYS = 30


@dataclass(frozen=True, slots=True)
class StorageCategory:
    key: str
    label: str
    bytes: int
    policy: str
    protected: bool


@dataclass(frozen=True, slots=True)
class StorageSnapshot:
    categories: tuple[StorageCategory, ...]

    @property
    def total_bytes(self) -> int:
        return sum(item.bytes for item in self.categories)


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    removed_items: int
    removed_bytes: int


def cache_root() -> Path:
    return Path(user_cache_dir("DubLocal"))


def data_root() -> Path:
    return Path(user_data_dir("DubLocal"))


def config_root() -> Path:
    return Path(user_config_dir("DubLocal"))


def app_home() -> Path:
    return Path.home() / ".dublocal"


def course_manifest_root() -> Path:
    return config_root() / "course-jobs"


def browser_profile_root() -> Path:
    return config_root() / "authenticated-web" / "profiles"


def managed_models_root() -> Path:
    return data_root() / "models"


def managed_runtimes_root() -> Path:
    return cache_root() / "runtimes"


def logs_root() -> Path:
    return app_home() / "logs"


def repair_backups_root() -> Path:
    return app_home() / "repair-backups"


def finished_output_roots() -> tuple[Path, ...]:
    return (
        Path.home() / "Downloads" / "DubLocal",
        Path.home() / "Movies" / "DubLocal",
        Path.home() / "DubLocal Outputs",
    )


def playwright_cache_root() -> Path:
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if configured and configured != "0":
        return Path(configured).expanduser()
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def _path_size(path: Path) -> int:
    try:
        if path.is_file() or path.is_symlink():
            return path.stat().st_size
    except OSError:
        return 0
    if not path.is_dir():
        return 0
    total = 0
    try:
        children = path.rglob("*")
        for child in children:
            try:
                if child.is_file() and not child.is_symlink():
                    total += child.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


def _roots_size(paths: tuple[Path, ...]) -> int:
    seen: set[Path] = set()
    total = 0
    for path in paths:
        try:
            identity = path.expanduser().resolve(strict=False)
        except OSError:
            identity = path.expanduser()
        if identity in seen:
            continue
        seen.add(identity)
        total += _path_size(path)
    return total


def storage_snapshot() -> StorageSnapshot:
    categories = (
        StorageCategory(
            "jobs",
            "Temporary jobs",
            _path_size(jobs_root()),
            f"Auto-pruned after {DEFAULT_MAX_AGE_HOURS} h and capped at {_human_size(DEFAULT_MAX_BYTES)} on startup.",
            False,
        ),
        StorageCategory(
            "translations",
            "Translation cache",
            _path_size(translation_cache_root()),
            "Reusable cache; automatically aged/capped and safe to clear.",
            False,
        ),
        StorageCategory(
            "models",
            "Installed models",
            _path_size(managed_models_root()),
            "Protected. Removed only through Model Manager.",
            True,
        ),
        StorageCategory(
            "runtimes",
            "Managed runtimes",
            _path_size(managed_runtimes_root()),
            "Protected optional runtimes such as Demucs/TTS environments.",
            True,
        ),
        StorageCategory(
            "shared_hf",
            "Shared Hugging Face cache",
            _path_size(shared_huggingface_cache()),
            "Shared/protected; never deleted by DubLocal cleanup.",
            True,
        ),
        StorageCategory(
            "browser_sessions",
            "Authenticated website sessions",
            _path_size(browser_profile_root()),
            "Protected sign-in state; clear only from Authenticated Websites settings.",
            True,
        ),
        StorageCategory(
            "browser_runtime",
            "Authenticated browser runtime",
            _path_size(playwright_cache_root()),
            "Current runtime protected; only old Chromium revisions are auto-pruned when safely identifiable.",
            True,
        ),
        StorageCategory(
            "course_manifests",
            "Course resume data",
            _path_size(course_manifest_root()),
            f"Tiny resume manifests; completed courses age out after {COURSE_DONE_RETENTION_DAYS} d, unfinished after {COURSE_UNFINISHED_RETENTION_DAYS} d.",
            True,
        ),
        StorageCategory(
            "logs",
            "Logs",
            _path_size(logs_root()),
            f"Rotated at {_human_size(LOG_ROTATE_BYTES)}; {LOG_KEEP} previous logs retained.",
            False,
        ),
        StorageCategory(
            "repair_backups",
            "Updater repair backups",
            _path_size(repair_backups_root()),
            f"Patch backups retained up to {REPAIR_RETENTION_DAYS} d, with at most {REPAIR_KEEP} recent backups.",
            True,
        ),
        StorageCategory(
            "outputs",
            "Finished DubLocal outputs",
            _roots_size(finished_output_roots()),
            "Protected user files. Automatic/manual cleanup never touches them. Local-file outputs beside originals are not scanned here.",
            True,
        ),
    )
    return StorageSnapshot(categories)


def _human_size(value: int) -> str:
    size = float(max(0, int(value)))
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TiB"


def storage_status_markdown() -> str:
    snapshot = storage_snapshot()
    lines = [
        "### Storage & Cleanup",
        "DubLocal separates disposable working data from protected models, sign-in state and finished outputs.",
        "",
        "| Category | Used | Policy |",
        "| --- | ---: | --- |",
    ]
    for item in snapshot.categories:
        protected = " Protected." if item.protected else ""
        lines.append(f"| {item.label} | {_human_size(item.bytes)} | {item.policy}{protected} |")
    lines.extend(
        [
            "",
            f"**Known DubLocal-managed/storage roots shown above:** {_human_size(snapshot.total_bytes)}.",
            "The cleanup action below removes only temporary jobs and translation cache entries, then applies normal retention policies. It cannot delete installed models, authenticated sessions, course outputs or finished media.",
        ]
    )
    return "\n".join(lines)


def _remove_path(path: Path) -> int:
    size = _path_size(path)
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    except OSError:
        return 0
    return size


def _clear_children(root: Path) -> CleanupSummary:
    if not root.is_dir():
        return CleanupSummary(0, 0)
    removed_items = 0
    removed_bytes = 0
    try:
        children = list(root.iterdir())
    except OSError:
        return CleanupSummary(0, 0)
    for child in children:
        size = _path_size(child)
        _remove_path(child)
        if not child.exists():
            removed_items += 1
            removed_bytes += size
    return CleanupSummary(removed_items, removed_bytes)


def prepare_log_for_launch() -> CleanupSummary:
    """Rotate the main launcher log before a new backend opens it for append."""

    root = logs_root()
    root.mkdir(parents=True, exist_ok=True)
    current = root / "dublocal.log"
    try:
        if not current.is_file() or current.stat().st_size < LOG_ROTATE_BYTES:
            return CleanupSummary(0, 0)
    except OSError:
        return CleanupSummary(0, 0)

    removed_bytes = 0
    oldest = root / f"dublocal.log.{LOG_KEEP}"
    if oldest.exists():
        removed_bytes += _remove_path(oldest)
    for index in range(LOG_KEEP - 1, 0, -1):
        source = root / f"dublocal.log.{index}"
        target = root / f"dublocal.log.{index + 1}"
        if source.exists():
            try:
                source.replace(target)
            except OSError:
                pass
    try:
        current.replace(root / "dublocal.log.1")
        return CleanupSummary(1, removed_bytes)
    except OSError:
        return CleanupSummary(0, removed_bytes)


def prune_course_manifests(*, now: float | None = None) -> CleanupSummary:
    root = course_manifest_root()
    if not root.is_dir():
        return CleanupSummary(0, 0)
    current = time.time() if now is None else float(now)
    removed_items = 0
    removed_bytes = 0
    for path in root.glob("*.json"):
        try:
            age_days = (current - path.stat().st_mtime) / 86400.0
        except OSError:
            continue
        finished = False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = dict(payload.get("items") or {}) if isinstance(payload, dict) else {}
            states = [str(item.get("state") or "") for item in items.values() if isinstance(item, dict)]
            finished = bool(states) and all(state == "done" for state in states)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            finished = False
        retention = COURSE_DONE_RETENTION_DAYS if finished else COURSE_UNFINISHED_RETENTION_DAYS
        if age_days <= retention:
            continue
        size = _path_size(path)
        _remove_path(path)
        if not path.exists():
            removed_items += 1
            removed_bytes += size
    return CleanupSummary(removed_items, removed_bytes)


def prune_repair_backups(*, now: float | None = None) -> CleanupSummary:
    root = repair_backups_root()
    if not root.is_dir():
        return CleanupSummary(0, 0)
    current = time.time() if now is None else float(now)
    entries: list[tuple[Path, float, int]] = []
    for path in root.glob("*.patch"):
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        entries.append((path, modified, _path_size(path)))

    remove: set[Path] = set()
    cutoff = current - REPAIR_RETENTION_DAYS * 86400
    for path, modified, _size in entries:
        if modified < cutoff:
            remove.add(path)
    kept = sorted((item for item in entries if item[0] not in remove), key=lambda item: item[1], reverse=True)
    for path, _modified, _size in kept[REPAIR_KEEP:]:
        remove.add(path)

    removed_items = 0
    removed_bytes = 0
    sizes = {path: size for path, _modified, size in entries}
    for path in remove:
        _remove_path(path)
        if not path.exists():
            removed_items += 1
            removed_bytes += sizes.get(path, 0)
    return CleanupSummary(removed_items, removed_bytes)


def _current_playwright_revision() -> tuple[Path, str] | None:
    root = playwright_cache_root()
    if not root.is_dir() or importlib.util.find_spec("playwright") is None:
        return None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as api:
            executable = Path(api.chromium.executable_path).resolve(strict=False)
        relative = executable.relative_to(root.resolve(strict=False))
    except Exception:
        return None
    if not relative.parts:
        return None
    folder = relative.parts[0]
    if not folder.startswith("chromium-"):
        return None
    revision = folder.split("-", 1)[1]
    return root, revision


def prune_old_playwright_revisions(*, now: float | None = None) -> CleanupSummary:
    detected = _current_playwright_revision()
    if detected is None:
        return CleanupSummary(0, 0)
    root, current_revision = detected
    current = time.time() if now is None else float(now)
    cutoff = current - PLAYWRIGHT_OLD_REVISION_DAYS * 86400
    removed_items = 0
    removed_bytes = 0
    try:
        children = list(root.iterdir())
    except OSError:
        return CleanupSummary(0, 0)
    for path in children:
        name = path.name
        if not (name.startswith("chromium-") or name.startswith("chromium_headless_shell-")):
            continue
        revision = name.rsplit("-", 1)[-1]
        if revision == current_revision:
            continue
        try:
            if path.stat().st_mtime >= cutoff:
                continue
        except OSError:
            continue
        size = _path_size(path)
        _remove_path(path)
        if not path.exists():
            removed_items += 1
            removed_bytes += size
    return CleanupSummary(removed_items, removed_bytes)


def prune_stale_jobs_only() -> CleanupSummary:
    result = prune_job_cache(max_age_hours=DEFAULT_MAX_AGE_HOURS, max_bytes=-1)
    return CleanupSummary(result.removed_items, result.removed_bytes)


def run_automatic_housekeeping() -> CleanupSummary:
    """Apply bounded automatic cleanup without touching models or finished outputs."""

    removed_items = 0
    removed_bytes = 0
    jobs = prune_job_cache(max_age_hours=DEFAULT_MAX_AGE_HOURS, max_bytes=DEFAULT_MAX_BYTES)
    removed_items += jobs.removed_items
    removed_bytes += jobs.removed_bytes
    prune_translation_cache()
    for summary in (prune_course_manifests(), prune_repair_backups(), prune_old_playwright_revisions()):
        removed_items += summary.removed_items
        removed_bytes += summary.removed_bytes
    return CleanupSummary(removed_items, removed_bytes)


def clean_temporary_files() -> CleanupSummary:
    """Clear disposable working/cache data only; protected data is never touched."""

    if job_active():
        raise RuntimeError("Stop the active DubLocal job before cleaning temporary files.")
    jobs = _clear_children(jobs_root())
    translations = _clear_children(translation_cache_root())
    removed_items = jobs.removed_items + translations.removed_items
    removed_bytes = jobs.removed_bytes + translations.removed_bytes
    for summary in (prune_course_manifests(), prune_repair_backups(), prune_old_playwright_revisions()):
        removed_items += summary.removed_items
        removed_bytes += summary.removed_bytes
    return CleanupSummary(removed_items, removed_bytes)


def clean_temporary_files_status() -> str:
    try:
        result = clean_temporary_files()
    except Exception as exc:
        return f"### Cleanup needs attention\n{exc}\n\n" + storage_status_markdown()
    return (
        f"### Temporary cleanup complete\nRemoved {result.removed_items} item(s), freeing approximately {_human_size(result.removed_bytes)}.\n\n"
        + storage_status_markdown()
    )
