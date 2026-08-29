from __future__ import annotations

import os
import shlex
import subprocess

from . import __version__
from .updater import (
    EXPECTED_BRANCH,
    EXPECTED_REMOTE,
    UpdateError,
    check_for_updates,
    install_update,
    repair_installation,
    repository_root,
)


def updater_idle_status() -> str:
    return (
        f"### DubLocal {__version__}\n"
        "Use **Update DubLocal** to check GitHub, install the newest safe version, and restart automatically."
    )


def _blocked_status(message: str) -> str:
    return f"### Update needs attention\n{message}"


def schedule_restart() -> None:
    """Detach the restart helper before the running backend is terminated.

    DubLocal's shutdown lifecycle deliberately kills all descendant helper processes.
    A restart helper left as a direct child of the running backend is therefore killed
    together with ffmpeg/model workers as soon as the launcher sends SIGTERM to the
    old process. Use a short bootstrap zsh that backgrounds/disowns the real restart
    command, wait for that bootstrap shell to exit, and only then return to the UI.
    The surviving helper is re-parented by macOS and can stop the old backend and
    launch the refreshed one safely.
    """

    root = repository_root()
    launcher = root / "scripts" / "macos" / "launch-dublocal.sh"
    if not launcher.is_file():
        raise UpdateError("The DubLocal macOS launcher script is missing.")

    command = (
        "(sleep 1; "
        "DUBLOCAL_LAUNCH_ACTION=restart "
        f"/bin/zsh {shlex.quote(str(launcher))}"
        ") </dev/null >/dev/null 2>&1 &!"
    )
    env = os.environ.copy()
    try:
        bootstrap = subprocess.Popen(
            ["/bin/zsh", "-c", command],
            cwd=str(root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        returncode = bootstrap.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"DubLocal could not schedule its restart: {exc}") from exc
    if returncode != 0:
        raise UpdateError("DubLocal could not detach the automatic restart helper.")


def update_dublocal_ui() -> str:
    """Normal-app update action: check, update/repair safely, then restart.

    A managed installation is allowed to replace modified tracked program files only
    after saving the existing patch through the updater's repair backup. Local commits,
    divergent history, non-main branches, and non-official upstreams remain protected.
    """

    try:
        status = check_for_updates(fetch_remote=True)
        expected_upstream = f"{EXPECTED_REMOTE}/{EXPECTED_BRANCH}"
        if status.branch != EXPECTED_BRANCH:
            return _blocked_status(
                f"This installation is on branch `{status.branch}`. Automatic update only manages `{EXPECTED_BRANCH}`."
            )
        if status.upstream != expected_upstream:
            return _blocked_status(
                f"This installation is not tracking `{expected_upstream}`. DubLocal will not rewrite a different Git checkout."
            )
        if status.diverged:
            return _blocked_status(
                "The local checkout and GitHub have diverged. No files were changed; review the Git history manually."
            )
        if status.ahead > 0:
            return _blocked_status(
                f"This checkout contains {status.ahead} local commit(s) that are not on GitHub. No files were changed."
            )

        if status.dirty:
            result = repair_installation(replace_modified_files=True)
            action = "repaired and updated"
        else:
            result = install_update()
            action = "updated" if result.changed else "repaired" if result.repaired else "checked"

        if not result.changed and not result.repaired:
            return (
                f"### DubLocal is up to date\n"
                f"You are running **{status.checkout_version}**. No restart is needed."
            )

        backup = f" A backup of replaced local program edits was saved at `{result.backup_path}`." if result.backup_path else ""
        if result.restart_required:
            schedule_restart()
            return (
                f"### DubLocal {action}\n"
                f"Installed **{status.remote_version}**.{backup} DubLocal is restarting automatically…"
            )
        return f"### DubLocal {action}\nThe installation is ready.{backup}"
    except Exception as exc:
        message = str(exc) if isinstance(exc, UpdateError) else f"Unexpected updater error: {exc}"
        return f"### Update failed\n{message}\n\nYour previous working installation was kept whenever rollback was possible."
