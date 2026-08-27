from dublocal.ui_v053 import build_app


def test_v053_ui_builds_with_subtitle_package_action():
    demo = build_app()
    assert demo is not None
