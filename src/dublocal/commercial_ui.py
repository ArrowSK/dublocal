from __future__ import annotations

from typing import Any

import gradio as gr

from . import cancellation_ui


_INSTALLED = False


def _copy(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    replacements = (
        ("Run Magic Flow", "Start Processing"),
        ("Magic Flow pipeline", "standard processing pipeline"),
        ("Magic Flow job", "processing job"),
        ("Magic Flow", "Standard workflow"),
        ("Simple is the default for normal use", "Standard is the default for normal use"),
        ("Simple/Auto", "Standard/Auto"),
    )
    result = value
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def _stop_processing() -> None:
    if not cancellation_ui.job_active():
        try:
            gr.Info("No processing job is currently running.")
        except Exception:
            pass
        return
    count = cancellation_ui.request_cancel()
    try:
        detail = (
            f" Stopping {count} active helper process{'es' if count != 1 else ''}."
            if count
            else ""
        )
        gr.Warning(
            "Stopping the current job. Completed outputs will be kept; queued items will not start."
            + detail
        )
    except Exception:
        pass


def install_commercial_ui(product_ui) -> None:
    """Apply product copy/labels without changing the underlying processing architecture."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    cancellation_ui._stop_magic_flow = _stop_processing

    original_run = product_ui._run_batch_magic_ui

    def run_with_product_copy(*args: Any, **kwargs: Any):
        result = original_run(*args, **kwargs)
        if not isinstance(result, tuple):
            return result
        return tuple(_copy(value) if isinstance(value, str) else value for value in result)

    product_ui._run_batch_magic_ui = run_with_product_copy

    original_build = product_ui.build_app

    def build_app_commercial():
        original_button = gr.Button
        original_html = gr.HTML
        original_markdown = gr.Markdown
        original_tab = gr.Tab
        original_accordion = gr.Accordion
        original_checkbox_group = gr.CheckboxGroup
        original_dropdown = gr.Dropdown
        original_file = gr.File

        def button_factory(value=None, *args: Any, **kwargs: Any):
            if value is not None:
                value = _copy(value)
            elif "value" in kwargs:
                kwargs = dict(kwargs)
                kwargs["value"] = _copy(kwargs.get("value"))
            return original_button(value, *args, **kwargs)

        def html_factory(value=None, *args: Any, **kwargs: Any):
            return original_html(_copy(value), *args, **kwargs)

        def markdown_factory(value=None, *args: Any, **kwargs: Any):
            return original_markdown(_copy(value), *args, **kwargs)

        def tab_factory(*args: Any, **kwargs: Any):
            updated_args = list(args)
            updated_kwargs = dict(kwargs)
            if updated_args and updated_args[0] == "Simple":
                updated_args[0] = "Standard"
            elif updated_kwargs.get("label") == "Simple":
                updated_kwargs["label"] = "Standard"
            return original_tab(*updated_args, **updated_kwargs)

        def accordion_factory(label=None, *args: Any, **kwargs: Any):
            mapping = {
                "More options": "Options",
                "Results": "Output files",
            }
            if label in mapping:
                label = mapping[label]
            return original_accordion(label, *args, **kwargs)

        def checkbox_group_factory(*args: Any, **kwargs: Any):
            updated = dict(kwargs)
            label = str(updated.get("label") or "")
            if label == "Create":
                updated["label"] = "Outputs"
            elif label == "Audio, voice & sharing":
                updated["label"] = "Audio & delivery"
            if "info" in updated:
                updated["info"] = _copy(updated.get("info"))
            return original_checkbox_group(*args, **updated)

        def dropdown_factory(*args: Any, **kwargs: Any):
            updated = dict(kwargs)
            label = str(updated.get("label") or "")
            if label == "Video quality":
                updated["label"] = "Resolution limit"
                updated["info"] = (
                    "Optional maximum resolution for this job. Compression is controlled by the saved per-format "
                    "Output Profile in Settings; Auto is recommended."
                )
            elif label == "Local transcription quality":
                updated["label"] = "Transcription quality"
            if "info" in updated:
                updated["info"] = _copy(updated.get("info"))
            return original_dropdown(*args, **updated)

        def file_factory(*args: Any, **kwargs: Any):
            updated = dict(kwargs)
            labels = {
                "Voice-only WAV": "Voice track · WAV",
                "Output media": "Media output",
            }
            if updated.get("label") in labels:
                updated["label"] = labels[updated["label"]]
            return original_file(*args, **updated)

        gr.Button = button_factory
        gr.HTML = html_factory
        gr.Markdown = markdown_factory
        gr.Tab = tab_factory
        gr.Accordion = accordion_factory
        gr.CheckboxGroup = checkbox_group_factory
        gr.Dropdown = dropdown_factory
        gr.File = file_factory
        try:
            return original_build()
        finally:
            gr.Button = original_button
            gr.HTML = original_html
            gr.Markdown = original_markdown
            gr.Tab = original_tab
            gr.Accordion = original_accordion
            gr.CheckboxGroup = original_checkbox_group
            gr.Dropdown = original_dropdown
            gr.File = original_file

    product_ui.build_app = build_app_commercial
