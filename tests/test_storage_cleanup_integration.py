from __future__ import annotations

from pathlib import Path


def test_storage_cleanup_is_installed_after_course_source_and_before_cancellation() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "src" / "dublocal" / "launcher_runtime.py").read_text(encoding="utf-8")

    course = runtime.index("install_course_import_ui(product_ui)")
    storage = runtime.index("install_storage_cleanup_ui(product_ui)")
    cancellation = runtime.index("install_cancellation_ui(product_ui)")

    assert course < storage < cancellation
    assert "run_automatic_housekeeping()" in runtime
    assert "prune_stale_jobs_only()" in runtime


def test_launcher_rotates_log_before_starting_backend() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "scripts" / "macos" / "launch-dublocal.sh").read_text(encoding="utf-8")

    rotate = launcher.index("prepare_log_for_launch")
    launch = launcher.index("-m dublocal.launcher_runtime >>\"$LOG_FILE\"")

    assert rotate < launch


def test_storage_settings_expose_safe_cleanup_action() -> None:
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "dublocal" / "storage_cleanup_ui.py").read_text(encoding="utf-8")

    assert 'gr.Accordion("Storage & Cleanup"' in ui
    assert 'gr.Button("Clean temporary files"' in ui
    assert "Installed models" in (root / "src" / "dublocal" / "storage_cleanup.py").read_text(encoding="utf-8")
    assert "Finished DubLocal outputs" in (root / "src" / "dublocal" / "storage_cleanup.py").read_text(encoding="utf-8")
