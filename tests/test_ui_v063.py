from __future__ import annotations

from dublocal.ui_v063 import build_app


def test_v063_ui_builds_with_batch_magic_and_single_updater() -> None:
    demo = build_app()
    assert demo is not None
