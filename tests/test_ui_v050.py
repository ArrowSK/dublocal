from dublocal.ui_v050 import build_app


def test_v050_ui_builds_with_m5_stage():
    demo = build_app()
    assert demo is not None
