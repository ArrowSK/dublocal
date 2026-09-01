from __future__ import annotations

from pathlib import Path


def test_storage_cleanup_is_an_explicit_launcher_service() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "src" / "dublocal" / "launcher_runtime.py").read_text(encoding="utf-8")

    assert "from .production_ui import MATRIX_CSS, build_app" in runtime
    assert "run_automatic_housekeeping()" in runtime
    assert "prune_stale_jobs_only()" in runtime
    assert "install_storage_cleanup_ui" not in runtime
    assert "install_course_import_ui" not in runtime
    assert "install_cancellation_ui" not in runtime


def test_launcher_rotates_log_before_starting_backend() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "scripts" / "macos" / "launch-dublocal.sh").read_text(encoding="utf-8")
    rotate = launcher.index("prepare_log_for_launch")
    launch = launcher.index("-m dublocal.launcher_runtime >>\"$LOG_FILE\"")
    assert rotate < launch


def test_storage_settings_expose_safe_cleanup_action_in_canonical_ui() -> None:
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "dublocal" / "production_ui.py").read_text(encoding="utf-8")
    cleanup = (root / "src" / "dublocal" / "storage_cleanup.py").read_text(encoding="utf-8")

    assert 'gr.Tab("Storage & Cleanup")' in ui
    assert 'gr.Button("Clean temporary files"' in ui
    assert "Installed models" in cleanup
    assert "Finished DubLocal outputs" in cleanup
