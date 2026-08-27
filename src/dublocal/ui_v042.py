from __future__ import annotations

import gradio as gr

from . import ui as base
from .adaptive_contextual import (
    active_recommendation,
    adaptive_contextual_translation_status,
    prepare_recommended_contextual_translation,
    remove_recommended_contextual_model,
)
from .dependencies import local_resource_status
from .hardware_profile import hardware_summary
from .progress import ProgressEstimator


_RECOMMENDATION = active_recommendation()

# Keep the ordinary workflow simple: one hardware-aware contextual choice plus the
# explicit legacy fast path. Detailed hardware/model reasoning stays in Settings.
base.contextual_translation_status = adaptive_contextual_translation_status
base.prepare_contextual_translation = prepare_recommended_contextual_translation
base.remove_contextual_model = remove_recommended_contextual_model
base.TRANSLATION_MODE_CHOICES = [
    (f"Recommended for this Mac · {_RECOMMENDATION.label}", "contextual"),
    ("Fast legacy · OPUS · sentence-level", "opus"),
]


def _prepare_contextual_settings(
    main_mode: str,
    main_source_language: str,
    main_target_language: str,
    source_info: dict | None,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    recommendation = active_recommendation()
    try:
        update(0.02, f"Checking llama.cpp and {recommendation.model_label}")
        prepared = prepare_recommended_contextual_translation()
        update(1.0, "Recommended contextual translation ready")
        action = (
            "```text\n"
            "[done] recommended contextual translation is ready\n"
            f"[hardware] {hardware_summary()}\n"
            f"[profile] {recommendation.label} · {recommendation.explanation}\n"
            f"[runtime/model] {prepared}\n"
            f"[review] {'on' if recommendation.review else 'off'}\n"
            f"[context cap] {recommendation.context_cap_tokens} input tokens\n"
            "```"
        )
    except Exception as exc:
        action = base._error_status(str(exc))
    settings_status = adaptive_contextual_translation_status("en", "ru", 0)
    main_status = base._translation_status_for_ui(
        main_mode,
        main_source_language,
        main_target_language,
        source_info,
    )
    return settings_status, main_status, local_resource_status(), action


def _remove_contextual_settings(
    main_mode: str,
    main_source_language: str,
    main_target_language: str,
    source_info: dict | None,
):
    recommendation = active_recommendation()
    try:
        removed = remove_recommended_contextual_model()
        action = (
            "```text\n"
            f"[model] recommended {recommendation.model_label} registration "
            f"{'removed' if removed else 'was not installed'}\n"
            "[shared cache] shared Hugging Face files are kept\n"
            "```"
        )
    except Exception as exc:
        action = base._error_status(str(exc))
    settings_status = adaptive_contextual_translation_status("en", "ru", 0)
    main_status = base._translation_status_for_ui(
        main_mode,
        main_source_language,
        main_target_language,
        source_info,
    )
    return settings_status, main_status, local_resource_status(), action


base._prepare_contextual_settings = _prepare_contextual_settings
base._remove_contextual_settings = _remove_contextual_settings


def build_app() -> gr.Blocks:
    """Build the v0.4.2 UI with a dynamic Model Manager title only."""

    original_accordion = base.gr.Accordion
    recommendation = active_recommendation()

    def accordion_with_quality_label(*args, **kwargs):
        if args and args[0] == "Contextual translation · Qwen3 4B":
            args = (
                f"Contextual translation · {recommendation.label} · {recommendation.model_label}",
                *args[1:],
            )
        return original_accordion(*args, **kwargs)

    base.gr.Accordion = accordion_with_quality_label
    try:
        return base.build_app()
    finally:
        base.gr.Accordion = original_accordion


MATRIX_CSS = base.MATRIX_CSS + r"""
/* Keep notices inside DubLocal's green/neutral visual language. */
.dl-quality-note {
  border-left-color: rgba(66, 239, 131, 0.62) !important;
  background: rgba(8, 28, 17, 0.34) !important;
  color: var(--dl-muted) !important;
}
"""
