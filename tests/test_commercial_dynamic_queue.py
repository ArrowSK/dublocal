from __future__ import annotations


def test_local_queue_button_does_not_restore_legacy_workflow_name():
    import dublocal.launcher_runtime  # noqa: F401 - installs production UI refinements
    import dublocal.product_ui as product_ui

    status, button = product_ui._local_queue_status(None)
    assert "Magic Flow" not in str(status)
    assert getattr(button, "value", None) == "Start Processing"
