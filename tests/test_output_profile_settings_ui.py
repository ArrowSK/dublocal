from __future__ import annotations


def test_output_profile_settings_offer_each_format_and_auto_profiles():
    import dublocal.launcher_runtime as launcher_runtime

    app = launcher_runtime.build_app()
    rendered = str(app.get_config_file())

    assert "Output profiles" in rendered
    assert "Auto · format-aware" in rendered
    assert "'label': 'MKV'" in rendered
    assert "'label': 'MP4'" in rendered
    assert "'label': 'Shareable MP4'" in rendered
    assert "Compact · sharing / storage" in rendered
    assert "Balanced · good quality / smaller file" in rendered
