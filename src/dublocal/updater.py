from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class UpdateError(RuntimeError):
    """Raised when DubLocal cannot safely check or apply an update."""


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

    @property
    def update_available(self) -> bool:
        return self.behind > 0 and self.ahead == 0

    @property
    def diverged(self) -> bool:
        return self.ahead > 0 and self.behind > 0


@dataclass(frozen=True, slots=True)
class UpdateResult:
    previous_revision: str
    current_revision: str
    changed: bool
    restart_required: bool


def repository_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        raise UpdateError(
            "This DubLocal installation is not a Git checkout, so the built-in updater is unavailable."
        )
    return root


def _run_git(root: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=check,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise UpdateError("Git is not installed or is not available to DubLocal.") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise UpdateError(message or "Git command failed.") from exc
    return (result.stdout or "").strip()


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

    candidate = f"origin/{branch}"
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


def check_for_updates(*, fetch_remote: bool = True) -> UpdateStatus:
    root = repository_root()
    branch = _run_git(root, "branch", "--show-current") or "detached"
    upstream = _upstream_ref(root)

    if fetch_remote:
        remote_name = upstream.split("/", 1)[0] if "/" in upstream else "origin"
        _run_git(root, "fetch", "--quiet", remote_name)

    local_revision = _run_git(root, "rev-parse", "HEAD")
    remote_revision = _run_git(root, "rev-parse", upstream)
    ahead, behind = _ahead_behind(root, upstream)
    dirty = bool(_run_git(root, "status", "--porcelain"))

    return UpdateStatus(
        repository=root,
        branch=branch,
        upstream=upstream,
        local_revision=local_revision,
        remote_revision=remote_revision,
        ahead=ahead,
        behind=behind,
        dirty=dirty,
    )


def format_update_status(status: UpdateStatus) -> str:
    local = status.local_revision[:12]
    remote = status.remote_revision[:12]
    lines = [
        f"[branch] {status.branch} → {status.upstream}",
        f"[current] {local}",
        f"[github]  {remote}",
    ]

    if status.dirty:
        lines.append("[safety] local changes detected · update blocked until they are resolved")
    elif status.diverged:
        lines.append(
            "[safety] local branch has diverged · "
            f"{status.ahead} ahead / {status.behind} behind · manual Git review required"
        )
    elif status.ahead > 0:
        lines.append(f"[status] local checkout is {status.ahead} commit(s) ahead of GitHub")
    elif status.behind > 0:
        lines.append(f"[update] {status.behind} new commit(s) available")
    else:
        lines.append("[status] DubLocal is up to date")

    return "```text\n" + "\n".join(lines) + "\n```"


def install_update() -> UpdateResult:
    status = check_for_updates(fetch_remote=True)

    if status.dirty:
        raise UpdateError(
            "DubLocal found local changes in its installation folder and will not overwrite them. "
            "Resolve or discard those changes first, then check again."
        )
    if status.diverged:
        raise UpdateError(
            "The local branch and GitHub have diverged. DubLocal will not guess which history to keep. "
            "Review the checkout with Git before updating."
        )
    if status.ahead > 0:
        raise UpdateError(
            "This checkout contains local commits that are not on GitHub. "
            "Automatic update is disabled for safety."
        )
    if status.behind == 0:
        return UpdateResult(
            previous_revision=status.local_revision,
            current_revision=status.local_revision,
            changed=False,
            restart_required=False,
        )

    root = status.repository
    previous = status.local_revision
    _run_git(root, "merge", "--ff-only", status.upstream)

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(root)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise UpdateError(
            "The Git update was downloaded, but DubLocal could not refresh its Python environment. "
            f"Restart may fail until dependencies are repaired. Details: {message}"
        ) from exc

    current = _run_git(root, "rev-parse", "HEAD")
    return UpdateResult(
        previous_revision=previous,
        current_revision=current,
        changed=current != previous,
        restart_required=current != previous,
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
