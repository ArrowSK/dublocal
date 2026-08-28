from __future__ import annotations

from typing import Any

import gradio as gr

from . import ui_v063 as previous
from .model_setup import (
    mark_first_run_skipped,
    model_setup_state,
    model_setup_summary,
    prepare_recommended_models,
)
from .progress import ProgressEstimator


# Keep this as the final visual layer. The selectors are intentionally scoped to
# Magic Flow/model setup so Advanced and the established global theme stay intact.
MATRIX_CSS = previous.MATRIX_CSS + r"""
.dl-magic-shell {
  padding: 18px !important;
}
.dl-magic-shell > .form,
.dl-magic-shell > .wrap {
  padding: 0 !important;
  margin: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.dl-magic-shell > * {
  box-sizing: border-box !important;
  margin-left: 0 !important;
  margin-right: 0 !important;
  max-width: 100% !important;
}
.dl-magic-shell .block:has(.dl-magic-title),
.dl-magic-shell .block:has(.dl-magic-subtitle),
.dl-magic-shell .block:has(.dl-compact-note),
.dl-magic-shell .dl-queue-note {
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.dl-magic-shell .block:has(.dl-magic-title),
.dl-magic-shell .block:has(.dl-magic-subtitle) {
  padding: 0 !important;
  margin: 0 !important;
  min-height: 0 !important;
}
.dl-magic-shell .dl-queue-note {
  padding: 2px 0 4px 0 !important;
  margin: 0 !important;
  min-height: 0 !important;
}
.dl-magic-shell .dl-stage-status {
  margin-left: 0 !important;
  margin-right: 0 !important;
  width: 100% !important;
}
.dl-magic-shell button.primary {
  width: 100% !important;
}

.dl-model-setup-card {
  border: 1px solid rgba(66, 239, 131, 0.50) !important;
  border-radius: 12px !important;
  padding: 18px !important;
  margin: 4px 0 18px 0 !important;
  background: rgba(7, 18, 11, 0.76) !important;
  box-shadow: none !important;
}
.dl-model-setup-card > .form,
.dl-model-setup-card > .wrap {
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.dl-model-setup-title {
  color: var(--dl-green) !important;
  font-size: 17px !important;
  font-weight: 700 !important;
  margin: 0 0 4px 0 !important;
}
.dl-model-setup-copy {
  color: var(--dl-muted) !important;
  font-size: 12px !important;
  margin: 0 0 10px 0 !important;
}
.dl-model-setup-summary {
  border: 0 !important;
  background: transparent !important;
  padding: 0 !important;
  margin: 2px 0 10px 0 !important;
  box-shadow: none !important;
}
.dl-model-setup-actions {
  align-items: stretch !important;
}
.dl-model-setup-actions button {
  min-height: 40px !important;
}
"""


def _setup_progress(progress: gr.Progress):
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    return update


def _prepare_setup_ui(
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    try:
        summary = prepare_recommended_models(progress_callback=_setup_progress(progress))
        try:
            gr.Info("Recommended DubLocal models are ready.")
        except Exception:
            pass
        return summary, gr.Column(visible=False)
    except Exception as exc:
        return (
            f"### Setup needs attention\n{exc}\n\nAnything already prepared was kept. You can run the wizard again.",
            gr.Column(visible=True),
        )


def _skip_first_run_ui():
    mark_first_run_skipped()
    return gr.Column(visible=False)


def _build_model_setup_card(*, first_run: bool) -> gr.Column:
    state = model_setup_state()
    panel = gr.Column(
        visible=(state.first_run_pending if first_run else True),
        elem_classes=["dl-model-setup-card"],
    )
    with panel:
        gr.HTML(
            '<div class="dl-model-setup-title">'
            + ("Welcome · model setup" if first_run else "Model Setup")
            + "</div>"
        )
        gr.HTML(
            '<div class="dl-model-setup-copy">'
            + (
                "DubLocal has chosen a practical local model set for this Mac. One action prepares subtitles, contextual translation and voice-over; nothing is downloaded until you approve it."
                if first_run
                else "Use the same simple hardware-aware setup at any time. It prepares or repairs only the models DubLocal recommends for this Mac. Detailed per-model controls remain under Advanced Models."
            )
            + "</div>"
        )
        status = gr.Markdown(
            model_setup_summary(),
            elem_classes=["dl-model-setup-summary"],
        )
        with gr.Row(elem_classes=["dl-model-setup-actions"]):
            prepare = gr.Button(
                "Set up recommended models" if first_run else "Prepare / repair recommended setup",
                variant="primary",
            )
            skip = None
            if first_run:
                skip = gr.Button("Skip for now", variant="secondary")

        begin = prepare.click(
            fn=lambda: "### Preparing recommended models…\nDubLocal will show the active download/preparation stage in the progress bar.",
            outputs=[status],
            queue=False,
        )
        begin.then(fn=_prepare_setup_ui, outputs=[status, panel])
        if skip is not None:
            skip.click(fn=_skip_first_run_ui, outputs=[panel], queue=False)
    return panel


def _build_batch_magic_panel_with_first_run(original_html) -> None:
    if model_setup_state().first_run_pending:
        _build_model_setup_card(first_run=True)
    previous._ORIGINAL_BATCH_MAGIC_PANEL(original_html)


# Keep a stable reference for the wrapper above and for tests. This is assigned at
# import time before build_app temporarily swaps the public symbol.
_ORIGINAL_BATCH_MAGIC_PANEL = previous._build_batch_magic_panel
previous._ORIGINAL_BATCH_MAGIC_PANEL = _ORIGINAL_BATCH_MAGIC_PANEL


class _ModelManagerTabsContext:
    """Put the simple wizard before the existing detailed model controls."""

    def __init__(self, original_tab, args, kwargs):
        self._original_tab = original_tab
        self._args = args
        self._kwargs = kwargs
        self._advanced = None

    def __enter__(self):
        with self._original_tab("Model Setup"):
            _build_model_setup_card(first_run=False)

        advanced_kwargs = dict(self._kwargs)
        if self._args:
            advanced_args = ("Advanced Models", *self._args[1:])
            self._advanced = self._original_tab(*advanced_args, **advanced_kwargs)
        else:
            advanced_kwargs["label"] = "Advanced Models"
            self._advanced = self._original_tab(**advanced_kwargs)
        return self._advanced.__enter__()

    def __exit__(self, exc_type, exc, tb):
        if self._advanced is None:
            return False
        return self._advanced.__exit__(exc_type, exc, tb)


def build_app() -> gr.Blocks:
    original_tab = gr.Tab
    original_batch_panel = previous._build_batch_magic_panel

    def tab_wrapper(*args: Any, **kwargs: Any):
        label = args[0] if args else kwargs.get("label")
        if label == "Model Manager":
            return _ModelManagerTabsContext(original_tab, args, kwargs)
        return original_tab(*args, **kwargs)

    gr.Tab = tab_wrapper
    previous._build_batch_magic_panel = _build_batch_magic_panel_with_first_run
    try:
        return previous.build_app()
    finally:
        gr.Tab = original_tab
        previous._build_batch_magic_panel = original_batch_panel
