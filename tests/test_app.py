from __future__ import annotations

from dublocal.app import _duration_label, _size_label, build_app


def test_display_helpers():
    assert _duration_label(None) == "unknown duration"
    assert _duration_label(65) == "1:05"
    assert _duration_label(3661) == "1:01:01"
    assert _size_label(1024) == "1.0 KB"


def test_gradio_app_builds():
    app = build_app()
    assert app is not None
