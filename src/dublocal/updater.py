from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import __version__


EXPECTED_REPOSITORY = "arrowsk/dublocal"
EXPECTED_BRANCH = "main"
EXPECTED_REMOTE = "origin"
_VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


class UpdateError(RuntimeError):
    """Raised when DubLocal cannot safely check, repair, or apply an update."""


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    repository: Path
    branch: str
    upstream: str
    local_revision: str
    remote_revision: str
    ahead: int
    behind: int
    dirty: bool
    current_version: str = "unknown"
    checkout_version: str = "unknown"
    remote_version: str = "unknown"
    repair_needed: bool = False
    dirty_paths: tuple[str, ...] = ()
    pending_commits: tuple[str, ...] = ()

    @property
    def update_available(self) -> bool:
        return self.behind > 0 and self.ahead == 0

    @property
    def diverged(self) -> bool:
        return self.ahead > 0 and self.behind > 0

    @property
    def can_update(self) -> bool:
        return (
            self.branch == EXPECTED_BRANCH
            and self.upstream == f"{EXPECTED_REMOTE}/{EXPECTED_BRANCH}"
            and not self.dirty
            and self.ahead == 0
            and (self.behind > 0 or self.repair_needed)
        )

    @property
    def can_repair_source(self) -> bool:
        return (
            self.branch == EXPECTED_BRANCH
            and self.upstream == f"{EXPECTED_REMOTE}/{EXPECTED_BRANCH}"
            and self.ahead == 0
            and not self.diverged
        )


@dataclass(frozen=True, slots=True)
class UpdateResult:
    previous_revision: str
    current_revision: str
    changed: bool
    restart_required: bool
    repaired: bool = False
    source_repaired: bool = False
    backup_path: Path | None = None


def repository_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        raise UpdateError(
            "This DubLocal installation is not a Git checkout, so the built-in updater is unavailable."
        )
    return root


def _run_git(root: Path, *args: str, check: bool = True) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
    except FileNotFoundError as exc:
        raise UpdateError("Git is not installed or is not available to DubLocal.") from exc
    except subprocess.TimeoutExpired as exc:
        raise UpdateError("Git did not finish within 90 seconds.") from exc
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "Git command failed.").strip()
        raise UpdateError(message.splitlines()[-1] if message else "Git command failed.")
    return (result.stdout or "").strip()


def _remote_identity(url: str) -> str | None:
    value = (url or "").strip()
    if value.startswith("git@github.com:"):
        path = value.split(":", 1)[1]
    elif "://" in value:
        parsed = urlparse(value)
        if (parsed.hostname or "").lower() != "github.com":
            return None
        path = parsed.path
    else:
        return None
    return path.strip("/").removesuffix(".git").lower() or None


def _verify_official_remote(root: Path) -> None:
    remote_url = _run_git(root, "remote", "get-url", EXPECTED_REMOTE)
    if _remote_identity(remote_url) != EXPECTED_REPOSITORY:
        raise UpdateError(
            "DubLocal refused automatic update because the configured origin is not "
            "ArrowSK/dublocal on GitHub."
        )


def _upstream_ref(root: Path) -> str:
    upstream = _run_git(
        root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        check=False,
    )
    if upstream:
        return upstream

    branch = _run_git(root, "branch", "--show-current")
    if not branch:
        raise UpdateError("DubLocal is on a detached Git revision and cannot update automatically.")

    candidate = f"{EXPECTED_REMOTE}/{branch}"
    exists = _run_git(root, "rev-parse", "--verify", candidate, check=False)
    if not exists:
        raise UpdateError(
            "This checkout has no configured upstream branch. Configure Git tracking before using the updater."
        )
    return candidate


def _ahead_behind(root: Path, upstream: str) -> tuple[int, int]:
    raw = _run_git(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    parts = raw.replace("\t", " ").split()
    if len(parts) != 2:
        raise UpdateError("Git returned an unexpected revision comparison result.")
    return int(parts[0]), int(parts[1])


def _version_from_init(text: str) -> str:
    match = _VERSION_RE.search(text)
    if not match:
        raise UpdateError("Could not read DubLocal's version from the selected revision.")
    return match.group(1)


def _version_at_revision(root: Path, revision: str) -> str:
    text = _run_git(root, "show", f"{revision}:src/dublocal/__init__.py")
    return _version_from_init(text)


def _tracked_status(root: Path) -> tuple[str, ...]:
    raw = _run_git(root, "status", "--porcelain", "--untracked-files=no")
    return tuple(line for line in raw.splitlines() if line.strip())


def check_for_updates(*, fetch_remote: bool = True) -> UpdateStatus:
    root = repository_root()
    _verify_official_remote(root)
    branch = _run_git(root, "branch", "--show-current") or "detached"
    upstream = _upstream_ref(root)

    if fetch_remote:
        _run_git(root, "fetch", "--quiet", EXPECTED_REMOTE, EXPECTED_BRANCH)

    local_revision = _run_git(root, "rev-parse", "HEAD")
    remote_revision = _run_git(root, "rev-parse", f"{EXPECTED_REMOTE}/{EXPECTED_BRANCH}")
    ahead, behind = _ahead_behind(root, f"{EXPECTED_REMOTE}/{EXPECTED_BRANCH}")
    dirty_paths = _tracked_status(root)
    checkout_version = _version_at_revision(root, local_revision)
    remote_version = (
        checkout_version
        if local_revision == remote_revision
        else _version_at_revision(root, remote_revision)
    )
    repair_needed = local_revision == remote_revision and __version__ != checkout_version

    pending: tuple[str, ...] = ()
    if behind > 0 and ahead == 0:
        raw = _run_git(
            root,
            "log",
            "--format=%h %s",
            "-n",
            "8",
            f"{local_revision}..{remote_revision}",
        )
        pending = tuple(line for line in raw.splitlines() if line.strip())

    return UpdateStatus(
        repository=root,
        branch=branch,
        upstream=upstream,
        local_revision=local_revision,
        remote_revision=remote_revision,
        ahead=ahead,
        behind=behind,
        dirty=bool(dirty_paths),
        current_version=__version__,
        checkout_version=checkout_version,
        remote_version=remote_version,
        repair_needed=repair_needed,
        dirty_paths=dirty_paths,
        pending_commits=pending,
    )


def format_update_status(status: UpdateStatus) -> str:
    local = status.local_revision[:12]
    remote = status.remote_revision[:12]
    lines = [
        f"[running] DubLocal v{status.current_version}",
        f"[local]   v{status.checkout_version} · {local}",
        f"[github]  v{status.remote_version} · {remote}",
    ]

    if status.branch != EXPECTED_BRANCH:
        lines.append(f"[safety] branch {status.branch!r} is not main · automatic update/repair blocked")
    elif status.diverged:
        lines.append(
            "[safety] local branch has diverged · "
            f"{status.ahead} ahead / {status.behind} behind · manual Git review required"
        )
    elif status.ahead > 0:
        lines.append(
            f"[safety] local checkout is {status.ahead} commit(s) ahead of GitHub · history is preserved"
        )
    elif status.dirty:
        lines.append(
            f"[repair] {len(status.dirty_paths)} modified tracked program file(s) detected · normal update blocked"
        )
        lines.append(
            "[repair] Repair installation can back up the patch, restore program files from GitHub, refresh the venv and restart"
        )
    elif status.behind > 0:
        lines.append(f"[update] {status.behind} new commit(s) available")
    elif status.repair_needed:
        lines.append(
            "[repair] Git checkout is current but the running Python core is stale · repair/restart recommended"
        )
    else:
        lines.append("[status] DubLocal is up to date and the running core matches the checkout")

    if status.pending_commits:
        lines.append("[changes] " + " | ".join(status.pending_commits[:4]))
    return "```text\n" + "\n".join(lines) + "\n```"


def _core_identity(root: Path) -> tuple[str, Path]:
    script = (
        "import json, dublocal; "
        "print(json.dumps({'version': dublocal.__version__, 'file': dublocal.__file__}))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(root),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"DubLocal core verification could not run: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "import failed").strip()
        raise UpdateError(f"DubLocal core import check failed: {detail.splitlines()[-1]}")
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        return str(payload["version"]), Path(str(payload["file"])).resolve()
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise UpdateError("DubLocal core returned an invalid import identity.") from exc


def _refresh_environment(root: Path, expected_version: str) -> None:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-e",
                str(root),
            ],
            cwd=str(root),
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"DubLocal could not refresh its Python environment: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "pip install failed").strip()
        raise UpdateError(
            "DubLocal could not refresh its Python environment: "
            + (detail.splitlines()[-1] if detail else "unknown pip error")
        )

    version, module_path = _core_identity(root)
    if version != expected_version:
        raise UpdateError(
            f"The refreshed core reports v{version}, but the checkout requires v{expected_version}."
        )
    expected_root = (root / "src" / "dublocal").resolve()
    try:
        module_path.relative_to(expected_root)
    except ValueError as exc:
        raise UpdateError(
            f"DubLocal imported from the wrong location: {module_path}. Expected {expected_root}."
        ) from exc


def _repair_backup(root: Path) -> Path | None:
    patch = _run_git(root, "diff", "--binary", "HEAD")
    if not patch.strip():
        return None
    backup_root = Path.home() / ".dublocal" / "repair-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_root / f"dublocal-local-changes-{timestamp}.patch"
    path.write_text(patch + "\n", encoding="utf-8")
    return path


def install_update() -> UpdateResult:
    status = check_for_updates(fetch_remote=True)

    if status.dirty:
        raise UpdateError(
            "DubLocal found modified tracked program files. Normal update will not overwrite them. "
            "Use Repair installation if you want DubLocal to back up those edits and restore the official files."
        )
    if status.diverged:
        raise UpdateError(
            "The local branch and GitHub have diverged. DubLocal will not guess which history to keep."
        )
    if status.ahead > 0:
        raise UpdateError(
            "This checkout contains local commits that are not on GitHub. Automatic update/repair is disabled for safety."
        )
    if status.branch != EXPECTED_BRANCH:
        raise UpdateError("Automatic update is available only from the main branch.")

    root = status.repository
    previous = status.local_revision
    revision_changed = status.behind > 0
    repaired = status.repair_needed and not revision_changed

    if not revision_changed and not repaired:
        return UpdateResult(
            previous_revision=previous,
            current_revision=previous,
            changed=False,
            restart_required=False,
        )

    try:
        if revision_changed:
            _run_git(root, "merge", "--ff-only", status.remote_revision)
        target_version = status.remote_version if revision_changed else status.checkout_version
        _refresh_environment(root, target_version)
    except Exception as exc:
        if revision_changed:
            try:
                _run_git(root, "reset", "--hard", previous)
                _refresh_environment(root, status.checkout_version)
            except Exception as rollback_exc:
                raise UpdateError(
                    f"Update failed: {exc}. Rollback also reported: {rollback_exc}"
                ) from exc
            raise UpdateError(f"Update failed: {exc}. The previous revision was restored.") from exc
        raise

    current = _run_git(root, "rev-parse", "HEAD")
    return UpdateResult(
        previous_revision=previous,
        current_revision=current,
        changed=current != previous,
        restart_required=True,
        repaired=repaired,
    )


def repair_installation(*, replace_modified_files: bool = False) -> UpdateResult:
    """Repair the managed core while protecting user data and developer history.

    With ``replace_modified_files=True`` tracked source edits are first backed up
    as a patch under ``~/.dublocal/repair-backups`` and then restored from
    ``origin/main``. Untracked files are not deleted. Local commits/diverged
    history are never rewritten by this repair path.
    """

    status = check_for_updates(fetch_remote=True)
    if status.branch != EXPECTED_BRANCH:
        raise UpdateError("Repair installation is available only on the main branch.")
    if status.diverged or status.ahead > 0:
        raise UpdateError(
            "Repair will not rewrite local commits or diverged Git history. Review this checkout manually first."
        )
    if status.dirty and not replace_modified_files:
        raise UpdateError(
            "Modified DubLocal program files were found. Tick the repair confirmation first. "
            "DubLocal will save a patch backup before replacing those tracked files."
        )

    root = status.repository
    previous = status.local_revision
    backup_path = _repair_backup(root) if status.dirty else None
    source_repaired = status.dirty

    try:
        if status.dirty:
            _run_git(root, "reset", "--hard", status.remote_revision)
        elif status.behind > 0:
            _run_git(root, "merge", "--ff-only", status.remote_revision)
        target_revision = _run_git(root, "rev-parse", "HEAD")
        target_version = _version_at_revision(root, target_revision)
        _refresh_environment(root, target_version)
    except Exception as exc:
        backup_note = f" Your edits were backed up to {backup_path}." if backup_path else ""
        raise UpdateError(f"Repair failed: {exc}.{backup_note}") from exc

    current = _run_git(root, "rev-parse", "HEAD")
    return UpdateResult(
        previous_revision=previous,
        current_revision=current,
        changed=current != previous,
        restart_required=True,
        repaired=True,
        source_repaired=source_repaired,
        backup_path=backup_path,
    )


def schedule_restart() -> None:
    root = repository_root()
    launcher = root / "scripts" / "macos" / "launch-dublocal.sh"
    if not launcher.is_file():
        raise UpdateError("The DubLocal macOS launcher script is missing.")

    command = (
        "sleep 1; "
        "DUBLOCAL_LAUNCH_ACTION=restart "
        f"/bin/zsh {shlex.quote(str(launcher))}"
    )
    env = os.environ.copy()
    subprocess.Popen(
        ["/bin/zsh", "-c", command],
        cwd=str(root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
