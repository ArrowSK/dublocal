from __future__ import annotations

import dublocal.ui as base_ui
import dublocal.ui_v042 as ui_v042


def test_quality_ui_rebinds_hardware_aware_contextual_status_and_choice():
    label, value = base_ui.TRANSLATION_MODE_CHOICES[0]
    assert value == "contextual"
    assert label.startswith("Recommended for this Mac · ")

    status = base_ui.contextual_translation_status("en", "ru", 60_000)
    assert "[recommended]" in status
    assert "[hardware]" in status
    assert "[model] Qwen3" in status
    assert "[context]" in status
    assert "[review]" in status
    assert "[policy] local-only; no cloud fallback" in status


def test_quality_ui_removes_orange_quality_note_accent():
    assert "border-left-color: rgba(66, 239, 131" in ui_v042.MATRIX_CSS
    assert "background: rgba(8, 28, 17" in ui_v042.MATRIX_CSS


def test_quality_ui_builds_with_adaptive_binding():
    demo = ui_v042.build_app()
    assert demo is not None
