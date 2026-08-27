from __future__ import annotations

import pytest

from dublocal.contextual_protocol import parse_line_translation
from dublocal.media import DubLocalError
from dublocal.timeline import Segment


def _targets() -> list[Segment]:
    return [
        Segment(index=25, start_ms=0, end_ms=1000, text="Hello"),
        Segment(index=26, start_ms=1000, end_ms=2000, text="World"),
    ]


def test_protocol_ignores_console_chatter_outside_markers():
    raw = (
        "Loading model... build b10621\n"
        "[25] source prompt echo\n"
        "DUBLOCAL_TRANSLATION_BEGIN\n"
        "[25] - Привет\n"
        "[26] - Мир\n"
        "DUBLOCAL_TRANSLATION_END\n"
        "Exiting..."
    )
    assert parse_line_translation(raw, _targets()) == ["Привет", "Мир"]


def test_protocol_refuses_unmarked_console_and_prompt_echo():
    raw = "Loading model...\n[25] source prompt echo\n[26] another prompt echo\nExiting..."
    with pytest.raises(DubLocalError):
        parse_line_translation(raw, _targets())
