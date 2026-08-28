from dublocal.ui_v060_refined import MATRIX_CSS, THEME_CONSISTENCY_CSS


def test_final_theme_keeps_gradio_loader_green() -> None:
    assert "--loader-color: var(--dl-green)" in THEME_CONSISTENCY_CSS
    assert "--loader-color-dark: var(--dl-green)" in THEME_CONSISTENCY_CSS
    assert '[data-testid="status-tracker"] .progress-bar' in THEME_CONSISTENCY_CSS
    assert "background-color: var(--dl-green)" in THEME_CONSISTENCY_CSS


def test_final_theme_covers_core_gradio_surfaces() -> None:
    required_tokens = (
        "--background-fill-primary",
        "--background-fill-secondary",
        "--block-background-fill",
        "--panel-background-fill",
        "--input-background-fill",
        "--input-border-color-focus",
        "--checkbox-background-color-selected",
        "--button-primary-background-fill",
        "--button-secondary-background-fill",
        "--table-even-background-fill",
        "--link-text-color",
    )
    for token in required_tokens:
        assert token in THEME_CONSISTENCY_CSS


def test_final_theme_is_last_css_layer() -> None:
    assert MATRIX_CSS.endswith(THEME_CONSISTENCY_CSS)
