from __future__ import annotations

import inspect

import dublocal.production_ui as production_ui


def test_local_queue_button_uses_commercial_product_copy():
    status, button = production_ui._local_queue_status(None)
    assert "Magic Flow" not in str(status)
    assert getattr(button, "value", None) == "Start Processing"


def test_local_queue_change_updates_note_and_processing_button():
    source = inspect.getsource(production_ui._build_standard)
    assert "outputs=[queue_note, run]" in source
    assert "local_files.change(" in source
