from __future__ import annotations

import dublocal.ui as base_ui
from dublocal import detailed_ui


def test_detailed_ui_uses_hardware_aware_contextual_translation() -> None:
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


def test_detailed_ui_keeps_green_quality_notice() -> None:
    assert "border-left-color: rgba(66, 239, 131" in detailed_ui.MATRIX_CSS
    assert "background: rgba(8, 28, 17" in detailed_ui.MATRIX_CSS


def test_detailed_ui_exposes_current_refinements() -> None:
    assert callable(detailed_ui._scan_source_ui)
    assert callable(detailed_ui._extract_ui)
    assert callable(detailed_ui._transcribe_ui)
    assert callable(detailed_ui._translate_with_state)
    assert callable(detailed_ui._generate_voice_ui)
    assert callable(detailed_ui._render_m5_ui)
    assert callable(detailed_ui._package_subtitles_ui)


def test_detailed_ui_builds_export_and_subtitle_package_workflow() -> None:
    demo = detailed_ui.build_app()
    assert demo is not None
