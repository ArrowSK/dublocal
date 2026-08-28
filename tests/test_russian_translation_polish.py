from __future__ import annotations

import inspect

from dublocal import cancellation_ui
from dublocal.contextual_policy import build_review_prompt, build_translation_prompt, context_plan
from dublocal.timeline import Segment
from dublocal.translation_quality import target_language_guidance, validate_translation_text


def _speaker_segments() -> list[Segment]:
    return [
        Segment(1, 0, 1500, "I feel strange today."),
        Segment(2, 1500, 3000, "I feel like a woman in this situation."),
        Segment(3, 3000, 4500, "When did I become so cold?"),
    ]


def test_russian_prompt_treats_first_person_gender_as_discourse_consistency():
    segments = _speaker_segments()
    prompt = build_translation_prompt(segments, 0, len(segments), "en", "ru", [], context_plan(segments))
    assert "RUSSIAN FIRST-PERSON CONSISTENCY" in prompt
    assert "comparison/metaphor noun does not change the narrator's gender" in prompt
    assert "avoids a gender-marked predicate rather than guessing" in prompt


def test_russian_review_requires_final_gender_and_case_audit():
    segments = _speaker_segments()
    prompt = build_translation_prompt(segments, 0, len(segments), "en", "ru", [], context_plan(segments))
    review = build_review_prompt(
        prompt,
        segments,
        ["Сегодня я странная.", "Я чувствую себя как женщина.", "Когда я стал таким холодным?"],
        "ru",
    )
    assert "RUSSIAN FINAL AUDIT" in review
    assert "must not alternate masculine/feminine forms" in review
    assert "noun gender, possessives/adjectives, governed case" in review


def test_russian_guidance_prefers_neutral_rephrase_when_gender_is_unknown():
    guidance = target_language_guidance("ru")
    assert "continuous first-person speaker" in guidance
    assert "gender-neutral Russian" in guidance
    assert "case government and agreement" in guidance


def test_protocol_id_echo_is_removed_but_unrelated_bracket_text_is_preserved():
    assert (
        validate_translation_text("[49] Пена — это то, где моё сердце.", target_language="ru", segment_id=49)
        == "Пена — это то, где моё сердце."
    )
    assert (
        validate_translation_text("[50] Это часть самой реплики.", target_language="ru", segment_id=49)
        == "[50] Это часть самой реплики."
    )


def test_magic_actions_are_one_balanced_non_destructive_row():
    source = inspect.getsource(cancellation_ui.install_cancellation_ui)
    css = cancellation_ui._STOP_CSS
    assert 'gr.Row(elem_classes=["dl-magic-actions"])' in source
    assert '"Stop"' in source
    assert 'variant="secondary"' in source
    assert ".dl-magic-actions" in css
    assert "flex: 2 1 0" in css
    assert "max-width: none" in css
    assert "margin-left: auto" not in css
