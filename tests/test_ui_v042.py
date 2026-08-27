from __future__ import annotations

import dublocal.ui as base_ui
import dublocal.ui_v042 as ui_v042


def test_quality_ui_rebinds_contextual_model_status_and_choices():
    assert base_ui.TRANSLATION_MODE_CHOICES[0] == (
        "Best quality · Qwen3 8B + review · recommended",
        "contextual",
    )
    status = base_ui.contextual_translation_status("en", "ru", 60_000)
    assert "Qwen3 8B" in status
    assert "5.03 GB" in status
    assert "Best mode adds a second context-aware review pass" in status


def test_quality_ui_removes_orange_quality_note_accent():
    assert "border-left-color: rgba(66, 239, 131" in ui_v042.MATRIX_CSS
    assert "background: rgba(8, 28, 17" in ui_v042.MATRIX_CSS


def test_quality_ui_builds_with_qwen3_8b_binding():
    demo = ui_v042.build_app()
    assert demo is not None
