from __future__ import annotations

import dublocal.production_ui as production_ui


def test_local_queue_button_uses_commercial_product_copy():
    status, button = production_ui._local_queue_status(None)
    assert "Magic Flow" not in str(status)
    assert getattr(button, "value", None) == "Start Processing"
