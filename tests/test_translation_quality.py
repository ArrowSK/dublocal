from __future__ import annotations

import pytest

from dublocal.media import DubLocalError
from dublocal.translation_quality import (
    clean_generated_text,
    is_protected_caption_tag,
    validate_translation_text,
)


def test_standalone_caption_tags_are_protected():
    assert is_protected_caption_tag("[MUSIC]")
    assert is_protected_caption_tag(" [APPLAUSE] [LAUGHTER] ")
    assert not is_protected_caption_tag("[MUSIC] Hello")


def test_control_characters_are_removed_without_destroying_unicode():
    assert clean_generated_text("Привет\b\x1b[31m!\x1b[0m") == "Привет!"


def test_cjk_contamination_is_rejected_for_current_targets():
    with pytest.raises(DubLocalError, match="unexpected non-target script"):
        validate_translation_text(
            "Где находится我的心?",
            target_language="ru",
            segment_id=12,
        )


def test_llama_runtime_text_is_never_accepted_as_subtitle_text():
    with pytest.raises(DubLocalError, match="runtime text"):
        validate_translation_text(
            "Loading model... Qwen3-4B-Q4_K_M.gguf",
            target_language="ru",
            segment_id=25,
        )
