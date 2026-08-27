from __future__ import annotations

import dublocal.app as app_module
from dublocal.app import MATRIX_CSS, _duration_label, _error_status, _size_label, build_app


def test_display_helpers():
    assert _duration_label(None) == "unknown duration"
    assert _duration_label(65) == "1:05"
    assert _duration_label(3661) == "1:01:01"
    assert _size_label(1024) == "1.0 KB"


def test_error_status_also_surfaces_visible_notification(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(app_module.gr, "Warning", lambda message: seen.append(message))

    status = _error_status("Confirm rights first.")

    assert seen == ["Confirm rights first."]
    assert "[error] Confirm rights first." in status


def test_base_css_forces_green_native_controls():
    assert '.gradio-container input[type="checkbox"]' in MATRIX_CSS
    assert '.gradio-container input[type="radio"]' in MATRIX_CSS
    assert "accent-color: var(--dl-green)" in MATRIX_CSS
    assert "--checkbox-background-color-selected: #42ef83" in MATRIX_CSS


def test_gradio_app_builds():
    app = build_app()
    assert app is not None
