from __future__ import annotations

import dublocal.launcher_runtime as launcher_runtime


def test_production_ui_builds_with_stop_and_course_controls() -> None:
    app = launcher_runtime.build_app()
    rendered = str(app.get_config_file())

    assert "Standard workflow" in rendered
    assert "Start Processing" in rendered
    assert "Stop" in rendered
    assert "dl-magic-actions" in rendered
    assert "Stop ends the current item and remaining queue" in rendered
    assert "Course / Website" in rendered
    assert "Course or lesson URL" in rendered
    assert "Open / Sign in" in rendered
    assert "Inspect course / lesson" in rendered
    assert "Authenticated Websites" in rendered
    assert "Prepare browser" in rendered
