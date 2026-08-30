from __future__ import annotations


def test_production_ui_uses_commercial_workflow_copy():
    import dublocal.launcher_runtime as launcher_runtime

    app = launcher_runtime.build_app()
    rendered = str(app.get_config_file())

    assert "Standard workflow" in rendered
    assert "Start Processing" in rendered
    assert "Output profiles" in rendered
    assert "Resolution limit" in rendered
    assert "Output files" in rendered
    assert "Magic Flow" not in rendered
    assert '"label":"Simple"' not in rendered
    assert "Standard" in rendered
