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
_MAGIC_AUDIO_PREFERENCE_CHOICES = [
    ("Keep original audio as a separate selectable track", "keep-original"),
    ("Single voice for the whole item · best overall match", "single-voice"),
    ("Burn subtitles into Shareable MP4 · always visible in messaging apps", "burn-share-subs"),
]
_SHAREABLE_OUTPUT_CHOICE = (
    "MP4 · Shareable · WhatsApp / Telegram · H.264 + AAC",
    "share",
)
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
.dl-audio-voice-prefs {
  margin: 2px 0 4px 0 !important;
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


def _apply_magic_audio_preferences(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Translate compact Audio, voice & sharing choices back into stable engine inputs."""

    values = list(args)
    if len(values) > 8 and isinstance(values[8], (list, tuple, set)):
        preferences = {str(item) for item in values[8]}
        tasks = [str(item) for item in (values[5] or [])]
        for marker in ("single-voice", "burn-share-subs"):
            if marker in preferences and marker not in tasks:
                tasks.append(marker)
        values[5] = tasks
        values[8] = "keep-original" in preferences
        return tuple(values), kwargs

    raw = kwargs.get("keep_original_audio_track")
    if isinstance(raw, (list, tuple, set)):
        preferences = {str(item) for item in raw}
        tasks = [str(item) for item in (kwargs.get("tasks") or [])]
        for marker in ("single-voice", "burn-share-subs"):
            if marker in preferences and marker not in tasks:
                tasks.append(marker)
        updated = dict(kwargs)
        updated["tasks"] = tasks
        updated["keep_original_audio_track"] = "keep-original" in preferences
        return args, updated
    return args, kwargs


def install_cancellation_ui(product_ui) -> None:
    """Layer production cancellation and compact Magic Flow controls onto the UI."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_run_ui = product_ui._run_batch_magic_ui

    def run_ui_with_lifecycle(*args: Any, **kwargs: Any):
        args, kwargs = _apply_magic_audio_preferences(args, kwargs)
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
        original_checkbox = gr.Checkbox
        original_dropdown = gr.Dropdown

        def button_factory(value=None, *args: Any, **kwargs: Any):
            label = str(value if value is not None else kwargs.get("value") or "")
            if label != "Run Magic Flow":
                return original_button(value, *args, **kwargs)

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

        def checkbox_factory(*args: Any, **kwargs: Any):
            label = str(kwargs.get("label") or "")
            if label != "Keep original audio as a separate selectable track":
                return original_checkbox(*args, **kwargs)
            return gr.CheckboxGroup(
                label="Audio, voice & sharing",
                choices=_MAGIC_AUDIO_PREFERENCE_CHOICES,
                value=["keep-original"],
                info=(
                    "Single voice uses one best-overall Kokoro voice throughout. Burn subtitles applies only to Shareable MP4 "
                    "and renders the intended translation (or source subtitles) permanently into the picture."
                ),
                elem_classes=["dl-audio-voice-prefs"],
            )

        def dropdown_factory(*args: Any, **kwargs: Any):
            label = str(kwargs.get("label") or "")
            if label != "Output format":
                return original_dropdown(*args, **kwargs)
            updated = dict(kwargs)
            choices = list(updated.get("choices") or [])
            if not any(isinstance(item, (list, tuple)) and len(item) >= 2 and item[1] == "share" for item in choices):
                choices.append(_SHAREABLE_OUTPUT_CHOICE)
            updated["choices"] = choices
            updated["info"] = (
                "Shareable MP4 keeps one intended audio track and produces messaging-friendly H.264/AAC with fast start. "
                "Enable Burn subtitles if the text must always be visible in WhatsApp/Telegram; standalone SRT files are still saved."
            )
            return original_dropdown(*args, **updated)

        gr.Button = button_factory
        gr.Checkbox = checkbox_factory
        gr.Dropdown = dropdown_factory
        try:
            demo = original_build()
        finally:
            gr.Button = original_button
            gr.Checkbox = original_checkbox
            gr.Dropdown = original_dropdown

        unload = getattr(demo, "unload", None)
        if callable(unload):
            unload(fn=release_session_resources)
        return demo

    product_ui.build_app = build_app_with_stop
