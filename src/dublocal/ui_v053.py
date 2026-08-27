from __future__ import annotations

from typing import Any

import gradio as gr

from . import ui_v050 as previous
from .caption_ux import caption_inventory_text, curate_caption_info
from .m53 import package_subtitled_media
from .progress import ProgressEstimator


base = previous.base
MATRIX_CSS = previous.MATRIX_CSS

_ORIGINAL_SCAN_UI = previous._scan_source_ui
_ORIGINAL_SOURCE_CARD_STATUS = base._source_card_status
_ORIGINAL_CAPTION_QUALITY_NOTE = base._caption_quality_note


def _scan_source_ui_human(*args, **kwargs):
    """Curate the raw subtitle inventory before it reaches the normal workflow."""

    result = list(_ORIGINAL_SCAN_UI(*args, **kwargs))
    if len(result) < 3 or not isinstance(result[2], dict) or not result[2]:
        return tuple(result)

    info = curate_caption_info(result[2])
    tracks = info.get("subtitle_tracks", []) or []
    choices = [(str(item.get("label") or "Subtitle track"), item.get("value")) for item in tracks]
    value = choices[0][1] if choices else None
    result[1] = gr.Dropdown(
        label="Available subtitles",
        choices=choices,
        value=value,
        interactive=bool(choices),
    )
    result[2] = info
    return tuple(result)


def _source_card_status_human(source_info: dict | None) -> str:
    info = source_info or {}
    if not info:
        return _ORIGINAL_SOURCE_CARD_STATUS(source_info)

    title = str(info.get("title") or "Media").replace("\n", " ").strip()
    kind = "YouTube" if info.get("kind") == "youtube" else "Local file"
    duration = base._duration_compact(info)
    visible = len(info.get("subtitle_tracks", []) or [])
    hidden = int(info.get("caption_hidden_count") or 0)

    if visible:
        subtitle_note = f"{visible} source subtitle track{'s' if visible != 1 else ''}"
    else:
        subtitle_note = "no usable existing subtitles"
    if hidden:
        subtitle_note += f" · {hidden} YouTube auto-translation{'s' if hidden != 1 else ''} hidden"
    return f"✓ **Loaded · OK** · {kind} · {title} · {duration} · {subtitle_note}"


def _caption_quality_note_human(info: dict | None, track_value: str | None) -> str:
    inventory = caption_inventory_text(info)
    selected_note = _ORIGINAL_CAPTION_QUALITY_NOTE(info, track_value)
    if inventory and selected_note:
        return f"**Available:** {inventory}\n\n{selected_note}"
    if inventory:
        return f"**Available:** {inventory}"
    return selected_note


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
    """Layer M5.3 stabilization and subtitle-inventory UX onto v0.5."""

    captured: dict[str, Any] = {}
    blanks: list[Any] = []
    package: dict[str, Any] = {}

    original_state = base.gr.State
    original_checkbox = base.gr.Checkbox
    original_dropdown = base.gr.Dropdown
    original_button = base.gr.Button
    original_previous_scan = previous._scan_source_ui
    original_source_card_status = base._source_card_status
    original_caption_quality_note = base._caption_quality_note

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
        label = kwargs.get("label") or ""
        if label == "Existing subtitle / caption track":
            kwargs["label"] = "Available subtitles"
            label = "Available subtitles"
        component = original_dropdown(*args, **kwargs)
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
    previous._scan_source_ui = _scan_source_ui_human
    base._source_card_status = _source_card_status_human
    base._caption_quality_note = _caption_quality_note_human
    try:
        demo = previous.build_app()
    finally:
        base.gr.State = original_state
        base.gr.Checkbox = original_checkbox
        base.gr.Dropdown = original_dropdown
        base.gr.Button = original_button
        previous._scan_source_ui = original_previous_scan
        base._source_card_status = original_source_card_status
        base._caption_quality_note = original_caption_quality_note

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
