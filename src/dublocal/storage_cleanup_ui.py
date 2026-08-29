from __future__ import annotations

from functools import wraps
from typing import Any

import gradio as gr

from .storage_cleanup import clean_temporary_files_status, prune_stale_jobs_only, storage_status_markdown


_INSTALLED = False


def _refresh_storage_ui() -> str:
    return storage_status_markdown()


def _clean_storage_ui() -> str:
    return clean_temporary_files_status()


def install_storage_cleanup_ui(product_ui) -> None:
    """Add one centralized storage view without changing processing UI behavior."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_settings = product_ui._build_settings_injections
    original_run_ui = product_ui._run_batch_magic_ui

    def settings_with_storage(original_html) -> None:
        original_settings(original_html)
        with gr.Accordion("Storage & Cleanup", open=False):
            status = gr.Markdown(storage_status_markdown(), elem_classes=["console"])
            original_html(
                '<div class="dl-note"><strong>Safe cleanup boundary:</strong> temporary jobs and translation cache can be cleared here. Installed models, authenticated website sessions, course resume state, managed runtimes and finished outputs are protected and are never removed by this action.</div>'
            )
            with gr.Row():
                refresh = gr.Button("Refresh storage usage", variant="secondary")
                clean = gr.Button("Clean temporary files", variant="primary")
            refresh.click(fn=_refresh_storage_ui, outputs=[status], queue=False)
            clean.click(fn=_clean_storage_ui, outputs=[status], queue=False)

    product_ui._build_settings_injections = settings_with_storage

    @wraps(original_run_ui)
    def run_ui_with_housekeeping(*args: Any, **kwargs: Any):
        try:
            return original_run_ui(*args, **kwargs)
        finally:
            # Only stale (>24 h) jobs are considered here. Current-session result files
            # remain available to the Gradio results panel until normal cache aging.
            try:
                prune_stale_jobs_only()
            except Exception:
                pass

    product_ui._run_batch_magic_ui = run_ui_with_housekeeping
