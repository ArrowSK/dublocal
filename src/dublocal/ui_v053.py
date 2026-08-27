from __future__ import annotations

from typing import Any

import gradio as gr

from . import ui_v050 as previous
from .m53 import package_subtitled_media
from .progress import ProgressEstimator


base = previous.base
MATRIX_CSS = previous.MATRIX_CSS


def _package_subtitles_ui(
    source_info: dict,
    rights_confirmed: bool,
    source_subtitle_path: str | None,
    source_language: str | None,
    container: str,
    video_quality: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    if not rights_confirmed:
        message = "Confirm that you have the right or legal authority to process this media before export."
        base._error_status(message)
        return None, f"⚠ **Subtitle package failed** · {message}"
    if not source_subtitle_path:
        message = "Extract or transcribe subtitles first. This export keeps the original audio and adds only that subtitle track."
        base._error_status(message)
        return None, f"⚠ **Subtitle package failed** · {message}"

    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    try:
        result = package_subtitled_media(
            source_info,
            source_subtitle_path,
            source_language,
            container=container,
            video_quality=video_quality,
            progress_callback=update,
        )
    except Exception as exc:
        message = str(exc)
        base._error_status(message)
        return None, f"⚠ **Subtitle package failed** · {message}"

    video_note = (
        "video stream copied · no re-encoding"
        if result.video_stream_copy
        else f"video encoded to selected {result.video_quality}p maximum"
    )
    return str(result.output_path), (
        f"✓ **Original + subtitles ready · OK** · {result.output_path.name} · {video_note} · "
        "original audio untouched · no translated subtitle embedded · no DubLocal voice/dub track embedded"
    )


def build_app() -> gr.Blocks:
    """Layer M5.3's subtitle-only package action onto the stable v0.5 workflow."""

    captured: dict[str, Any] = {}
    blanks: list[Any] = []
    package: dict[str, Any] = {}

    original_state = base.gr.State
    original_checkbox = base.gr.Checkbox
    original_dropdown = base.gr.Dropdown
    original_button = base.gr.Button

    def state_wrapper(value=None, *args, **kwargs):
        component = original_state(value, *args, **kwargs)
        if "source_state" not in captured and isinstance(value, dict):
            captured["source_state"] = component
        elif value == "" and len(blanks) < 2:
            blanks.append(component)
            if len(blanks) == 1:
                captured["subtitle_path"] = component
        return component

    def checkbox_wrapper(*args, **kwargs):
        component = original_checkbox(*args, **kwargs)
        label = kwargs.get("label") or (args[0] if args and isinstance(args[0], str) else "")
        if "right or legal authority" in str(label):
            captured["rights"] = component
        return component

    def dropdown_wrapper(*args, **kwargs):
        component = original_dropdown(*args, **kwargs)
        label = kwargs.get("label") or ""
        if label == "From":
            captured["source_language"] = component
        elif label == "Container":
            captured["container"] = component
        elif label == "Video quality":
            captured["quality"] = component
        return component

    def button_wrapper(*args, **kwargs):
        label = args[0] if args and isinstance(args[0], str) else kwargs.get("value")
        component = original_button(*args, **kwargs)
        if label == "Create dubbed media" and not package:
            package["button"] = original_button(
                "Package original + subtitles · no dub",
                variant="secondary",
            )
            package["status"] = gr.Markdown(
                "**Optional** · original audio/video + source subtitles only.",
                elem_classes=["dl-stage-status"],
            )
            package["output"] = gr.File(
                label="Original media with subtitles",
                interactive=False,
            )
        return component

    base.gr.State = state_wrapper
    base.gr.Checkbox = checkbox_wrapper
    base.gr.Dropdown = dropdown_wrapper
    base.gr.Button = button_wrapper
    try:
        demo = previous.build_app()
    finally:
        base.gr.State = original_state
        base.gr.Checkbox = original_checkbox
        base.gr.Dropdown = original_dropdown
        base.gr.Button = original_button

    required = {
        "source_state",
        "subtitle_path",
        "rights",
        "source_language",
        "container",
        "quality",
    }
    if package and required.issubset(captured):
        with demo:
            begin = package["button"].click(
                fn=lambda: "**Packaging original media + subtitles…** · no dub or translation track will be added.",
                outputs=[package["status"]],
                queue=False,
            )
            begin.then(
                fn=_package_subtitles_ui,
                inputs=[
                    captured["source_state"],
                    captured["rights"],
                    captured["subtitle_path"],
                    captured["source_language"],
                    captured["container"],
                    captured["quality"],
                ],
                outputs=[package["output"], package["status"]],
            )

    return demo
