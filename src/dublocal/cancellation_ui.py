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
/* Final Magic Flow spacing and action hierarchy. Keep this scoped so Advanced
   and Settings retain their established layout. */
.dl-magic-shell {
  padding: 20px 22px !important;
}
.dl-magic-shell .dl-magic-title {
  margin: 0 0 4px 0 !important;
}
.dl-magic-shell .dl-magic-subtitle {
  margin: 0 0 14px 0 !important;
  line-height: 1.45 !important;
}
.dl-magic-shell .dl-queue-note,
.dl-magic-shell .dl-compact-note {
  line-height: 1.45 !important;
}
.dl-magic-shell .dl-stage-status {
  margin: 8px 0 6px 0 !important;
  padding: 10px 12px !important;
  border: 1px solid rgba(43, 108, 66, 0.62) !important;
  border-radius: 8px !important;
  background: rgba(7, 18, 11, 0.58) !important;
  box-sizing: border-box !important;
}
.dl-magic-actions {
  display: flex !important;
  align-items: stretch !important;
  gap: 12px !important;
  margin: 12px 0 6px 0 !important;
  width: 100% !important;
}
.dl-magic-actions > * {
  min-width: 0 !important;
  margin: 0 !important;
}
.dl-magic-actions button {
  min-height: 44px !important;
  width: 100% !important;
  margin: 0 !important;
  border-radius: 8px !important;
  font-weight: 650 !important;
}
.dl-magic-actions button.primary {
  flex: 2 1 0 !important;
}
.dl-stop-button {
  flex: 1 1 0 !important;
  max-width: none !important;
  margin: 0 !important;
  background: #101b15 !important;
  border: 1px solid rgba(66, 239, 131, 0.52) !important;
  color: var(--dl-green-soft) !important;
  box-shadow: none !important;
}
.dl-stop-button:hover {
  background: #16271d !important;
  border-color: rgba(66, 239, 131, 0.82) !important;
  color: var(--dl-text) !important;
}
.dl-stop-note {
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: var(--dl-muted) !important;
  font-size: 11px !important;
  line-height: 1.4 !important;
  padding: 0 2px !important;
  margin: 0 0 10px 0 !important;
}
.dl-magic-shell .accordion {
  margin-top: 4px !important;
  margin-bottom: 4px !important;
}
.dl-magic-shell .accordion > .label-wrap {
  padding-left: 14px !important;
  padding-right: 14px !important;
}
.dl-magic-shell .accordion .form {
  padding-left: 14px !important;
  padding-right: 14px !important;
}
.dl-magic-shell .block,
.dl-magic-shell .form,
.dl-magic-shell .wrap {
  box-sizing: border-box !important;
}
.dl-magic-shell .gradio-row {
  gap: 14px !important;
}
.dl-magic-shell .dl-queue-note + * {
  margin-top: 2px !important;
}

@media (max-width: 720px) {
  .dl-magic-shell {
    padding: 16px !important;
  }
  .dl-magic-actions {
    flex-direction: column !important;
    gap: 8px !important;
  }
  .dl-magic-actions button.primary,
  .dl-stop-button {
    flex: 1 1 auto !important;
  }
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
            label = str(value if value is not None else kwargs.get("value") or "")
            if label != "Run Magic Flow":
                return original_button(value, *args, **kwargs)

            # The primary Run action and secondary Stop action belong to the same
            # decision row. Creating both inside one Row keeps them aligned while
            # preserving the original Run component/event wiring.
            with gr.Row(elem_classes=["dl-magic-actions"]):
                button = original_button(value, *args, **kwargs)
                stop = original_button(
                    "Stop",
                    variant="secondary",
                    elem_classes=["dl-stop-button"],
                )
            stop.click(fn=_stop_magic_flow, queue=False)
            gr.Markdown(
                "Stop ends the current item and remaining queue; completed files stay. Closing this page also releases active model/tool processes.",
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
