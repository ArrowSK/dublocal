from __future__ import annotations

from pathlib import Path


def test_storage_cleanup_ui_does_not_replace_existing_settings_layers() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "src" / "dublocal" / "launcher_runtime.py").read_text(encoding="utf-8")
    course_ui = (root / "src" / "dublocal" / "course_import_ui.py").read_text(encoding="utf-8")
    storage_ui = (root / "src" / "dublocal" / "storage_cleanup_ui.py").read_text(encoding="utf-8")

    assert 'gr.Accordion("Authenticated Websites"' in course_ui
    assert 'gr.Accordion("Storage & Cleanup"' in storage_ui
    assert "original_settings(original_html)" in storage_ui
    assert launcher.index("install_course_import_ui(product_ui)") < launcher.index("install_storage_cleanup_ui(product_ui)")
