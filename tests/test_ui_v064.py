from __future__ import annotations

from dublocal import ui_v064


def test_v064_ui_builds_with_first_run_and_model_setup_layers(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_v064,
        "model_setup_state",
        lambda: type("State", (), {"first_run_pending": False})(),
    )
    demo = ui_v064.build_app()
    assert demo is not None


def test_v064_final_css_flattens_magic_flow_and_styles_model_setup() -> None:
    css = ui_v064.MATRIX_CSS
    assert ".dl-model-setup-card" in css
    assert ".dl-magic-shell > .form" in css
    assert ":has(.dl-magic-title)" in css
    assert ".dl-queue-note" in css
