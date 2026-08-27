from __future__ import annotations

from dublocal.contextual_recovery import build_format_repair_prompt, recover_chunk_output
from dublocal.timeline import Segment


def _targets() -> list[Segment]:
    return [
        Segment(index=1, start_ms=0, end_ms=1000, text="Hello."),
        Segment(index=2, start_ms=1000, end_ms=2000, text="How are you?"),
    ]


def test_legacy_plain_text_recovery_parser_preserves_alignment():
    """Keep the tolerant parser covered for old cached/debug model responses."""

    assert recover_chunk_output(
        "[1] - Привет.\n[2] - Как ты?\n",
        _targets(),
    ) == ["Привет.", "Как ты?"]


def test_legacy_repair_prompt_uses_non_json_line_protocol():
    prompt = build_format_repair_prompt("bad output", _targets(), "Russian")
    assert "[ID] - translated text" in prompt
    assert "Do not output JSON" in prompt
    assert "Required subtitle ids, exactly once and in this order: 1, 2" in prompt
