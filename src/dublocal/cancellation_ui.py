from __future__ import annotations

from typing import Any

import gradio as gr

from .job_control import (
    begin_job,
    cancel_requested,
    end_job,
    job_active,
    release_session_resources,
    request_cancel,
)


_INSTALLED = False
_STOP_CSS = r"""
.dl-stop-button {
  max-width: 190px !important;
  margin-left: auto !important;
  margin-top: 6px !important;
}
.dl-stop-note {
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: var(--dl-muted) !important;
  font-size: 12px !important;
  padding: 0 !important;
  margin: 2px 0 8px 0 !important;
}
"""


def _stop_magic_flow() -> None:
    if not job_active():
        try:
            gr.Info("No Magic Flow job is currently running.")
        except Exception:
            pass
        return
    count = request_cancel()
    try:
        detail = f" Stopping {count} active helper process{'es' if count != 1 else ''}." if count else ""
        gr.Warning("Stopping the current job. Completed outputs will be kept; queued items will not start." + detail)
    except Exception:
        pass


def _rows_cancelled(rows: Any) -> tuple[int, int]:
    if not isinstance(rows, list):
        return 0, 0
    cancelled = 0
    done = 0
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        state = str(row[2]).upper()
        if state == "CANCELLED":
            cancelled += 1
        elif state == "DONE":
            done += 1
    return done, cancelled


def install_cancellation_ui(product_ui) -> None:
    """Layer production cancellation onto the consolidated product UI.

    This is intentionally narrow: it preserves the existing Magic Flow layout and
    pipeline while adding a Stop control, cancellation state, and browser-unload
    cleanup. It can be folded into product_ui during the next runtime consolidation.
    """

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_run_ui = product_ui._run_batch_magic_ui

    def run_ui_with_lifecycle(*args: Any, **kwargs: Any):
        begin_job()
        try:
            outputs = original_run_ui(*args, **kwargs)
            was_cancelled = cancel_requested()
            if isinstance(outputs, tuple) and len(outputs) >= 6:
                values = list(outputs)
                done, cancelled = _rows_cancelled(values[4])
                if was_cancelled or cancelled:
                    total = len(values[4]) if isinstance(values[4], list) else done + cancelled
                    values[5] = (
                        f"■ **Queue stopped** · {done}/{total} completed · "
                        f"{cancelled or max(0, total - done)} cancelled/not started · "
                        "completed outputs were kept."
                    )
                outputs = tuple(values)
            return outputs
        finally:
            end_job()

    product_ui._run_batch_magic_ui = run_ui_with_lifecycle
    product_ui.MATRIX_CSS += _STOP_CSS

    original_build = product_ui.build_app

    def build_app_with_stop():
        original_button = gr.Button

        def button_factory(value=None, *args: Any, **kwargs: Any):
            button = original_button(value, *args, **kwargs)
            label = str(value if value is not None else kwargs.get("value") or "")
            if label == "Run Magic Flow":
                stop = original_button(
                    "STOP current job",
                    variant="stop",
                    elem_classes=["dl-stop-button"],
                )
                stop.click(fn=_stop_magic_flow, queue=False)
                gr.Markdown(
                    "Stop cancels the current item and the remaining queue while keeping completed files. Closing this page also releases active model/tool processes.",
                    elem_classes=["dl-stop-note"],
                )
            return button

        gr.Button = button_factory
        try:
            demo = original_build()
        finally:
            gr.Button = original_button

        unload = getattr(demo, "unload", None)
        if callable(unload):
            unload(fn=release_session_resources)
        return demo

    product_ui.build_app = build_app_with_stop
