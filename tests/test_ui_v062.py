from __future__ import annotations

from dublocal.tts_provider_refinement import _apply_provider_metadata
from dublocal.ui_v062 import build_app


def test_v062_ui_builds_with_russian_provider_controls() -> None:
    _apply_provider_metadata()
    demo = build_app()
    assert demo is not None
