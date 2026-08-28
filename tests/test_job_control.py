from __future__ import annotations

import subprocess
import sys

from dublocal.job_control import (
    begin_job,
    cancel_requested,
    end_job,
    job_active,
    release_session_resources,
    request_cancel,
    start_process,
    tracked_process_count,
)


def _sleep_command() -> list[str]:
    return [sys.executable, "-c", "import time; time.sleep(30)"]


def test_request_cancel_terminates_explicitly_tracked_helper() -> None:
    begin_job()
    process = start_process(_sleep_command())
    try:
        assert job_active()
        assert tracked_process_count() == 1
        killed = request_cancel()
        process.wait(timeout=3)
        assert killed >= 1
        assert process.poll() is not None
        assert cancel_requested()
        assert tracked_process_count() == 0
    finally:
        end_job()

    assert not job_active()
    assert not cancel_requested()


def test_request_cancel_also_terminates_legacy_untracked_descendant() -> None:
    begin_job()
    process = subprocess.Popen(_sleep_command())
    try:
        killed = request_cancel()
        process.wait(timeout=3)
        assert killed >= 1
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        end_job()


def test_browser_unload_releases_active_helper_without_quitting_test_process() -> None:
    begin_job()
    process = subprocess.Popen(_sleep_command())
    try:
        release_session_resources()
        process.wait(timeout=3)
        assert process.poll() is not None
        assert cancel_requested()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        end_job()
