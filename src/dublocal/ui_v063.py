from __future__ import annotations

from typing import Any

import gradio as gr

from . import ui_v060 as simple
from . import ui_v062 as previous
from .batch_flow import download_groups, queue_rows, run_magic_queue
from .normal_update import update_dublocal_ui, updater_idle_status
from .progress import ProgressEstimator


MATRIX_CSS = previous.MATRIX_CSS + r"""
.dl-queue-note {
  margin: 6px 0 10px 0 !important;
  color: var(--dl-muted) !important;
  font-size: 12px !important;
}
.dl-update-card {
  border: 1px solid rgba(66, 239, 131, 0.46) !important;
  border-radius: 12px !important;
  padding: 14px !important;
  background: rgba(7, 18, 11, 0.72) !important;
}
.dl-update-card h3 {
  margin: 0 0 4px 0 !important;
  color: var(--dl-green-soft) !important;
}
"""


def _toggle_batch_source(source_type: str):
    youtube = source_type == "YouTube"
    return (
        gr.Textbox(visible=youtube),
        gr.File(visible=not youtube, file_count="multiple"),
        (
            "Paste one video, playlist, or channel URL. Collections are expanded into one sequential queue."
            if youtube
            else "Choose one or more files. They are processed one at a time, never in parallel."
        ),
    )


def _local_queue_status(files: Any) -> tuple[str, Any]:
    if not files:
        return "Choose one or more local media files.", gr.Button(value="Run Magic Flow")
    if isinstance(files, (str, bytes)) or getattr(files, "name", None):
        count = 1
    else:
        count = len(list(files))
    label = "file" if count == 1 else "files"
    return (
        f"**{count} {label} selected** · one shared queue · sequential processing · outputs are saved next to each source file.",
        gr.Button(value=f"Run {count} queued {label}"),
    )


def _run_batch_magic_ui(
    source_type: str,
    youtube_url: str,
    local_files: Any,
    rights_confirmed: bool,
    target_language: str,
    tasks: list[str] | None,
    subtitle_policy: str,
    keep_original_audio_track: bool,
    container: str,
    video_quality: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    try:
        result = run_magic_queue(
            source_type=source_type,
            youtube_url=youtube_url,
            local_files=local_files,
            rights_confirmed=rights_confirmed,
            target_language=target_language,
            tasks=tasks,
            subtitle_policy=subtitle_policy,
            keep_original_audio_track=keep_original_audio_track,
            container=container,
            video_quality=video_quality,
            progress_callback=update,
        )
    except Exception as exc:
        return [], [], [], [], [], f"⚠ **Queue failed to start** · {exc}"

    source_outputs, translated_outputs, voice_outputs, media_outputs = download_groups(result)
    done = len(result.succeeded)
    failed = len(result.failed)
    total = len(result.items)
    if source_type == "Local file":
        location = "finished outputs were also saved next to each original local file"
    else:
        location = "finished outputs were also saved in Downloads/DubLocal"
    if failed:
        status = (
            f"⚠ **Queue complete** · {done}/{total} succeeded · {failed} failed · {location}. "
            "Failed items are listed below; successful items were kept and the queue continued."
        )
    else:
        status = f"✓ **Queue complete · OK** · {done}/{total} succeeded · {location}."
    return (
        source_outputs,
        translated_outputs,
        voice_outputs,
        media_outputs,
        queue_rows(result),
        status,
    )


def _build_batch_magic_panel(original_html) -> None:
    with gr.Group(elem_classes=["dl-magic-shell"]):
        original_html('<div class="dl-magic-title">Magic Flow</div>')
        original_html(
            '<div class="dl-magic-subtitle">One video or many: choose the source and desired result. DubLocal expands the input into a single queue and runs the existing pipeline one item at a time.</div>'
        )

        source_type = gr.Radio(
            choices=["YouTube", "Local file"],
            value="YouTube",
            label="Source",
        )
        youtube_url = gr.Textbox(
            label="YouTube video, playlist, or channel",
            placeholder="https://www.youtube.com/watch?v=… · /playlist?list=… · /@channel",
        )
        local_files = gr.File(
            label="Local media",
            file_types=["video", "audio"],
            file_count="multiple",
            type="filepath",
            visible=False,
        )
        queue_note = gr.Markdown(
            "Paste one video, playlist, or channel URL. Collections are expanded into one sequential queue.",
            elem_classes=["dl-queue-note"],
        )
        source_type.change(
            fn=_toggle_batch_source,
            inputs=[source_type],
            outputs=[youtube_url, local_files, queue_note],
            queue=False,
        )

        rights = gr.Checkbox(
            label="I have the right or legal authority to process this media",
            value=False,
        )

        with gr.Row():
            target_language = gr.Dropdown(
                label="Output language",
                choices=simple.base.TARGET_LANGUAGE_CHOICES,
                value="en",
                interactive=True,
            )
            tasks = gr.CheckboxGroup(
                label="Create",
                choices=simple.MAGIC_TASK_CHOICES,
                value=["subtitles", "translate", "voice", "media"],
            )

        with gr.Accordion("More options", open=False):
            original_html(
                '<div class="dl-compact-note">The same settings apply to every queued item. A failed item does not discard successful items or stop the rest of the queue.</div>'
            )
            subtitle_policy = gr.Dropdown(
                label="Subtitle source",
                choices=simple.MAGIC_SUBTITLE_POLICY_CHOICES,
                value="auto",
            )
            keep_original_audio = gr.Checkbox(
                label="Keep original audio as a separate selectable track",
                value=True,
            )
            with gr.Row():
                container = gr.Dropdown(
                    label="Output format",
                    choices=simple.CONTAINER_CHOICES,
                    value="mkv",
                )
                quality = gr.Dropdown(
                    label="Video quality",
                    choices=simple.VIDEO_QUALITY_CHOICES,
                    value="source",
                )
            original_html(
                '<div class="dl-compact-note"><strong>Local files:</strong> generated SRT, voice and media outputs are copied beside each source. <strong>YouTube:</strong> persistent copies go to Downloads/DubLocal. The files shown below remain the normal in-app results.</div>'
            )

        run = gr.Button("Run Magic Flow", variant="primary")
        local_files.change(
            fn=_local_queue_status,
            inputs=[local_files],
            outputs=[queue_note, run],
            queue=False,
        )
        status = gr.Markdown(
            "**Ready** · each item uses the normal Magic Flow pipeline; queue work is strictly sequential.",
            elem_classes=["dl-stage-status"],
        )

        with gr.Accordion("Results", open=False):
            with gr.Row():
                source_output = gr.File(
                    label="Source subtitles",
                    file_count="multiple",
                    interactive=False,
                )
                translated_output = gr.File(
                    label="Translated subtitles",
                    file_count="multiple",
                    interactive=False,
                )
            with gr.Row():
                voice_output = gr.File(
                    label="Voice-only WAV",
                    file_count="multiple",
                    interactive=False,
                )
                media_output = gr.File(
                    label="Output media",
                    file_count="multiple",
                    interactive=False,
                )
            queue_table = gr.Dataframe(
                headers=["#", "Item", "State", "Saved output / error"],
                datatype=["str", "str", "str", "str"],
                interactive=False,
                wrap=True,
            )

        begin = run.click(
            fn=lambda: "**Running queue…** · items are processed one by one; the progress bar shows the current item and overall position.",
            outputs=[status],
            queue=False,
        )
        begin.then(
            fn=_run_batch_magic_ui,
            inputs=[
                source_type,
                youtube_url,
                local_files,
                rights,
                target_language,
                tasks,
                subtitle_policy,
                keep_original_audio,
                container,
                quality,
            ],
            outputs=[
                source_output,
                translated_output,
                voice_output,
                media_output,
                queue_table,
                status,
            ],
        )


class _UpdatesTabContext:
    """Replace the developer-style updater controls with one normal app action."""

    def __init__(self, original_tab, args, kwargs):
        self._original_tab = original_tab
        self._args = args
        self._kwargs = kwargs
        self._tab = None
        self._legacy = None

    def __enter__(self):
        self._tab = self._original_tab(*self._args, **self._kwargs)
        result = self._tab.__enter__()
        with gr.Group(elem_classes=["dl-update-card"]):
            status = gr.Markdown(updater_idle_status())
            button = gr.Button("Update DubLocal", variant="primary")
            gr.HTML(
                '<div class="dl-note">One action checks the official main branch, installs a safe fast-forward (or repairs managed program files with a patch backup when needed), refreshes the environment, and restarts DubLocal automatically. Local commits and diverged Git history are never overwritten.</div>'
            )
            begin = button.click(
                fn=lambda: "### Checking for updates…\nDubLocal is checking the official GitHub main branch.",
                outputs=[status],
                queue=False,
            )
            begin.then(fn=update_dublocal_ui, outputs=[status])

        # The stable UI still creates/wires the old updater controls. Keep them alive
        # but invisible so this layer changes only UX, not the proven updater engine.
        self._legacy = gr.Column(visible=False)
        self._legacy.__enter__()
        return result

    def __exit__(self, exc_type, exc, tb):
        suppress = False
        if self._legacy is not None:
            suppress = bool(self._legacy.__exit__(exc_type, exc, tb)) or suppress
        if self._tab is not None:
            suppress = bool(self._tab.__exit__(exc_type, exc, tb)) or suppress
        return suppress


def build_app() -> gr.Blocks:
    original_tab = gr.Tab
    original_magic_panel = simple._build_magic_panel

    def tab_wrapper(*args: Any, **kwargs: Any):
        label = args[0] if args else kwargs.get("label")
        if label == "Updates":
            return _UpdatesTabContext(original_tab, args, kwargs)
        return original_tab(*args, **kwargs)

    gr.Tab = tab_wrapper
    simple._build_magic_panel = _build_batch_magic_panel
    try:
        return previous.build_app()
    finally:
        gr.Tab = original_tab
        simple._build_magic_panel = original_magic_panel
