from __future__ import annotations

from pathlib import Path


def test_storage_and_authenticated_settings_share_canonical_ui_without_wrappers() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "src" / "dublocal" / "launcher_runtime.py").read_text(encoding="utf-8")
    ui = (root / "src" / "dublocal" / "production_ui.py").read_text(encoding="utf-8")

    assert 'gr.Tab("Authenticated Websites")' in ui
    assert 'gr.Tab("Storage & Cleanup")' in ui
    assert "install_course_import_ui" not in launcher
    assert "install_storage_cleanup_ui" not in launcher
    assert "original_settings(original_html)" not in ui
