from __future__ import annotations

import gradio as gr

from . import ui as base
from .contextual_quality_model import (
    prepare_quality_contextual_translation,
    quality_contextual_translation_status,
    remove_quality_contextual_model,
)
from .dependencies import local_resource_status
from .progress import ProgressEstimator


# Keep this small adapter while the v0.4 UI is being stabilized. It lets the quality
# backend change without duplicating the large Gradio layout. The next structural UI
# refactor can fold these bindings back into ui.py.
base.contextual_translation_status = quality_contextual_translation_status
base.prepare_contextual_translation = prepare_quality_contextual_translation
base.remove_contextual_model = remove_quality_contextual_model
base.TRANSLATION_MODE_CHOICES = [
    ("Best quality · Qwen3 8B + review · recommended", "contextual"),
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

    try:
        update(0.02, "Checking llama.cpp and Qwen3 8B")
        prepared = prepare_quality_contextual_translation()
        update(1.0, "High-quality contextual translation ready")
        action = (
            "```text\n"
            "[done] high-quality contextual translation is ready\n"
            f"[runtime/model] {prepared}\n"
            "[engine] Qwen3 8B Q4_K_M through llama.cpp\n"
            "[mode] translation + context-aware senior review pass\n"
            "```"
        )
    except Exception as exc:
        action = base._error_status(str(exc))
    settings_status = quality_contextual_translation_status("en", "ru", 0)
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
    try:
        removed = remove_quality_contextual_model()
        action = (
            "```text\n"
            f"[model] Qwen3 8B DubLocal registration {'removed' if removed else 'was not installed'}\n"
            "[shared cache] shared Hugging Face files are kept\n"
            "```"
        )
    except Exception as exc:
        action = base._error_status(str(exc))
    settings_status = quality_contextual_translation_status("en", "ru", 0)
    main_status = base._translation_status_for_ui(
        main_mode,
        main_source_language,
        main_target_language,
        source_info,
    )
    return settings_status, main_status, local_resource_status(), action


base._prepare_contextual_settings = _prepare_contextual_settings
base._remove_contextual_settings = _remove_contextual_settings


# The only remaining literal 4B label is the Model Manager accordion title. Replace
# that exact presentation string while constructing the UI; no other Accordion is touched.
def build_app() -> gr.Blocks:
    original_accordion = base.gr.Accordion

    def accordion_with_quality_label(*args, **kwargs):
        if args and args[0] == "Contextual translation · Qwen3 4B":
            args = ("Contextual translation · Qwen3 8B · quality", *args[1:])
        return original_accordion(*args, **kwargs)

    base.gr.Accordion = accordion_with_quality_label
    try:
        return base.build_app()
    finally:
        base.gr.Accordion = original_accordion


MATRIX_CSS = base.MATRIX_CSS + r"""
/* Keep warnings inside DubLocal's green/neutral visual language. */
.dl-quality-note {
  border-left-color: rgba(66, 239, 131, 0.62) !important;
  background: rgba(8, 28, 17, 0.34) !important;
  color: var(--dl-muted) !important;
}
"""
