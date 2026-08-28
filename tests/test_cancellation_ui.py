from __future__ import annotations

import dublocal.launcher_runtime as launcher_runtime


def test_production_magic_flow_builds_with_stop_and_course_controls() -> None:
    app = launcher_runtime.build_app()
    config = app.get_config_file()
    rendered = str(config)

    assert "Stop" in rendered
    assert "dl-magic-actions" in rendered
    assert "Closing this page also releases active model/tool processes" in rendered
    assert "Course / Website" in rendered
    assert "Course or lesson URL" in rendered
    assert "Open / Sign in" in rendered
    assert "Inspect course / lesson" in rendered
    assert "Authenticated Websites" in rendered
    assert "Prepare authenticated website browser" in rendered
    assert "YouTube / Course website URL" in rendered
