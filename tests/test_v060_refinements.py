from __future__ import annotations

import dublocal.m53 as m53
import dublocal.product_ui as product_ui
import dublocal.v060_refinements as refinements


def test_audio_balance_refinement_lowers_resting_original_bed():
    original = m53._ORIGINAL_BED_GAIN
    try:
        refinements.install_audio_balance_refinement()
        assert m53._ORIGINAL_BED_GAIN == 0.45
        assert m53._ORIGINAL_BED_GAIN < 0.62
    finally:
        m53._ORIGINAL_BED_GAIN = original


def test_magic_flow_media_label_explains_subtitle_only_path():
    labels = {value: label for label, value in product_ui.MAGIC_TASK_CHOICES}
    assert "original + subtitles" in labels["media"].lower()
    assert "translate/voice" in labels["media"].lower()


def test_canonical_product_ui_builds():
    demo = product_ui.build_app()
    assert demo is not None
