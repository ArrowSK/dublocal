from __future__ import annotations

import atexit
import gc
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from typing import Any


class JobCancelled(RuntimeError):
    """Raised when the user stops the active DubLocal job."""


_LOCK = threading.RLock()
_CANCEL = threading.Event()
_ACTIVE = threading.Event()
_PROCESSES: dict[int, subprocess.Popen[Any]] = {}
_HOOKS_INSTALLED = False


def begin_job() -> None:
    """Start one user job and clear cancellation left by an earlier run."""

    _CANCEL.clear()
    _ACTIVE.set()


def end_job() -> None:
    _ACTIVE.clear()
    _CANCEL.clear()


def job_active() -> bool:
    return _ACTIVE.is_set()


def cancel_requested() -> bool:
    return _CANCEL.is_set()


def check_cancelled() -> None:
    if _CANCEL.is_set():
        raise JobCancelled("Stopped by user.")


def _register(process: subprocess.Popen[Any]) -> subprocess.Popen[Any]:
    with _LOCK:
        _PROCESSES[process.pid] = process
    return process


def unregister_process(process: subprocess.Popen[Any]) -> None:
    with _LOCK:
        _PROCESSES.pop(process.pid, None)


def tracked_process_count() -> int:
    with _LOCK:
        stale = [pid for pid, process in _PROCESSES.items() if process.poll() is not None]
        for pid in stale:
            _PROCESSES.pop(pid, None)
        return len(_PROCESSES)


def start_process(command: Sequence[str] | str, **kwargs: Any) -> subprocess.Popen[Any]:
    """Start a subprocess explicitly owned by the current DubLocal job."""

    check_cancelled()
    kwargs.setdefault("start_new_session", True)
    process = subprocess.Popen(command, **kwargs)
    return _register(process)


def _signal_process(process: subprocess.Popen[Any], sig: int) -> None:
    if process.poll() is not None:
        unregister_process(process)
        return
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), sig)
        elif sig == signal.SIGTERM:
            process.terminate()
        else:
            process.kill()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            if sig == signal.SIGTERM:
                process.terminate()
            else:
                process.kill()
        except (ProcessLookupError, OSError):
            pass


def _descendant_pids(root_pid: int | None = None) -> set[int]:
    """Return current descendant PIDs without relying on optional psutil.

    Much of DubLocal predates central process tracking and starts ffmpeg, whisper.cpp,
    llama.cpp, Demucs and TTS workers directly. Discovering descendants lets the Stop
    button protect those established paths immediately, without killing unrelated
    model processes owned by other applications.
    """

    if os.name != "posix":
        return set()
    parent = int(root_pid or os.getpid())
    try:
        result = subprocess.run(
            ["/bin/ps", "-axo", "pid=,ppid="],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()

    children: dict[int, set[int]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            pid, ppid = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        children.setdefault(ppid, set()).add(pid)

    descendants: set[int] = set()
    frontier = list(children.get(parent, ()))
    while frontier:
        pid = frontier.pop()
        if pid in descendants or pid == parent:
            continue
        descendants.add(pid)
        frontier.extend(children.get(pid, ()))
    return descendants


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def terminate_all_processes(*, grace_seconds: float = 1.5) -> int:
    """Terminate active DubLocal helper descendants and explicitly tracked processes.

    Only descendants of this DubLocal backend are discovered, so an unrelated
    llama-server/ffmpeg process started by the user or another app is never targeted.
    """

    with _LOCK:
        tracked = [process for process in _PROCESSES.values() if process.poll() is None]
    descendants = _descendant_pids()
    targeted = set(descendants)
    targeted.update(process.pid for process in tracked)
    if not targeted:
        return 0

    tracked_pids = {process.pid for process in tracked}
    for process in tracked:
        _signal_process(process, signal.SIGTERM)
    for pid in descendants - tracked_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    deadline = time.monotonic() + max(0.0, float(grace_seconds))
    while time.monotonic() < deadline:
        if not any(_pid_alive(pid) for pid in targeted):
            break
        time.sleep(0.05)

    for process in tracked:
        if process.poll() is None:
            _signal_process(process, signal.SIGKILL)
    for pid in descendants - tracked_pids:
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    for process in tracked:
        try:
            process.wait(timeout=0.5)
        except (subprocess.TimeoutExpired, OSError):
            pass
        unregister_process(process)
    return len(targeted)


def request_cancel() -> int:
    """Request cooperative cancellation and immediately stop blocking child tools."""

    _CANCEL.set()
    return terminate_all_processes()


def run_process(
    command: Sequence[str] | str,
    *,
    capture_output: bool = False,
    text: bool = False,
    check: bool = False,
    timeout: float | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Cancellation-aware equivalent of the subprocess.run subset DubLocal uses."""

    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout/stderr cannot be supplied with capture_output=True")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    kwargs["text"] = text
    process = start_process(command, **kwargs)
    started = time.monotonic()
    stdout = None
    stderr = None
    try:
        while True:
            check_cancelled()
            wait_for = 0.25
            if timeout is not None:
                remaining = float(timeout) - (time.monotonic() - started)
                if remaining <= 0:
                    _signal_process(process, signal.SIGTERM)
                    try:
                        stdout, stderr = process.communicate(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        _signal_process(process, signal.SIGKILL)
                        stdout, stderr = process.communicate()
                    raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
                wait_for = min(wait_for, remaining)
            try:
                stdout, stderr = process.communicate(timeout=wait_for)
                break
            except subprocess.TimeoutExpired:
                continue

        check_cancelled()
        completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if check and process.returncode:
            raise subprocess.CalledProcessError(
                process.returncode,
                command,
                output=stdout,
                stderr=stderr,
            )
        return completed
    finally:
        unregister_process(process)


def _release_in_process_accelerator_cache() -> None:
    """Free accelerator caches only when Torch is already loaded in this process."""

    torch = sys.modules.get("torch")
    if torch is None:
        return
    try:
        mps = getattr(getattr(torch, "mps", None), "empty_cache", None)
        if callable(mps):
            mps()
    except Exception:
        pass
    try:
        cuda = getattr(torch, "cuda", None)
        if cuda is not None and callable(getattr(cuda, "empty_cache", None)):
            cuda.empty_cache()
    except Exception:
        pass


def release_session_resources() -> None:
    """Release heavyweight work when the browser session goes away.

    The lightweight local Gradio server may remain available for a later reopen, but
    model/tool child processes must not keep consuming unified memory invisibly.
    """

    if job_active():
        request_cancel()
    else:
        terminate_all_processes()
    _release_in_process_accelerator_cache()
    gc.collect()


def shutdown_all() -> None:
    _CANCEL.set()
    terminate_all_processes(grace_seconds=1.0)
    _ACTIVE.clear()
    _release_in_process_accelerator_cache()


def install_shutdown_hooks() -> None:
    """Install idempotent process-exit hooks for launcher stop/restart and Ctrl-C."""

    global _HOOKS_INSTALLED
    with _LOCK:
        if _HOOKS_INSTALLED:
            return
        _HOOKS_INSTALLED = True
    atexit.register(shutdown_all)

    def handler(signum, _frame) -> None:
        shutdown_all()
        raise SystemExit(128 + int(signum))

    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
