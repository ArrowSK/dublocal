from __future__ import annotations

import dublocal.launcher_runtime as launcher_runtime


def test_production_magic_flow_builds_with_stop_control() -> None:
    app = launcher_runtime.build_app()
    config = app.get_config_file()
    rendered = str(config)

    assert "Stop" in rendered
    assert "dl-magic-actions" in rendered
    assert "Closing this page also releases active model/tool processes" in rendered
