from __future__ import annotations

from dublocal.ui import _translation_route_languages, build_app


def test_translation_model_routes():
    assert _translation_route_languages("en-to-many") == ("en", "hu")
    assert _translation_route_languages("many-to-en") == ("hu", "en")
    assert _translation_route_languages("both") == ("hu", "de")


def test_tabbed_ui_builds():
    demo = build_app()
    assert demo is not None
