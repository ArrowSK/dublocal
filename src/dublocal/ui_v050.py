from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import gradio as gr

from . import app as app_module
from . import ui_v042 as previous
from .language_utils import normalize_language_code
from .m5 import CONTAINER_CHOICES, OUTPUT_MODE_CHOICES, render_dubbed_media
from .output_naming import friendly_subtitle_path
from .progress import ProgressEstimator
from .subtitle_export import export_subtitle
from .voice_text import prepare_voice_srt


base = previous.base
MATRIX_CSS = previous.MATRIX_CSS

_LAST_SOURCE_INFO: dict[str, Any] = {}
_LAST_SOURCE_LANGUAGE = "auto"

_ORIGINAL_SCAN = base._scan_source_ui
_ORIGINAL_EXTRACT = base._extract_ui
_ORIGINAL_TRANSCRIBE = base._transcribe_ui
_ORIGINAL_TRANSLATE = base._translate_with_state
_ORIGINAL_GENERATE_UI = base._generate_voice_ui
_ORIGINAL_VOICE_PROGRESS = base.generate_voice_track_with_progress


def _remember_source(info: dict[str, Any] | None) -> None:
    global _LAST_SOURCE_INFO
    if info:
        _LAST_SOURCE_INFO = dict(info)


def _with_language_normalizer(fn: Callable[..., Any], *args, **kwargs):
    original = app_module.normalise_language_code
    app_module.normalise_language_code = normalize_language_code
    try:
        return fn(*args, **kwargs)
    finally:
        app_module.normalise_language_code = original


def _scan_source_ui(*args, **kwargs):
    global _LAST_SOURCE_LANGUAGE
    result = _ORIGINAL_SCAN(*args, **kwargs)
    if len(result) >= 3 and isinstance(result[2], dict) and result[2]:
        _remember_source(result[2])
        # A newly loaded source must not inherit language metadata from the prior job.
        _LAST_SOURCE_LANGUAGE = "auto"
    return result


def _friendly_subtitle_result(
    path: str | None,
    language: str | None,
    output_format: str,
) -> tuple[str | None, str]:
    if not path:
        return None, ""
    friendly = friendly_subtitle_path(path, _LAST_SOURCE_INFO, language)
    exported = export_subtitle(friendly, output_format)
    return str(exported), str(friendly)


def _extract_ui(
    info: dict,
    track_value: str | None,
    rights_confirmed: bool,
    output_format: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    global _LAST_SOURCE_LANGUAGE
    _remember_source(info)
    download, rows, status, path, language, card = _with_language_normalizer(
        _ORIGINAL_EXTRACT,
        info,
        track_value,
        rights_confirmed,
        output_format,
        progress,
    )
    resolved = normalize_language_code(language)
    if path and resolved != "auto":
        _LAST_SOURCE_LANGUAGE = resolved
    if path:
        old_name = Path(path).name
        download, path = _friendly_subtitle_result(path, resolved, output_format)
        status = status.replace(old_name, Path(path).name)
    language_update = gr.Dropdown(
        choices=base.LANGUAGE_CHOICES,
        value=resolved,
        interactive=True,
    )
    return download, rows, status, path, language_update, card


def _transcribe_ui(
    info: dict,
    rights_confirmed: bool,
    model_id: str,
    language: str,
    output_format: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    global _LAST_SOURCE_LANGUAGE
    _remember_source(info)
    download, rows, status, path, detected, card = _with_language_normalizer(
        _ORIGINAL_TRANSCRIBE,
        info,
        rights_confirmed,
        model_id,
        language,
        output_format,
        progress,
    )
    resolved = normalize_language_code(detected)
    if resolved == "auto" and language != "auto":
        resolved = normalize_language_code(language)
    if path and resolved != "auto":
        _LAST_SOURCE_LANGUAGE = resolved
    if path:
        old_name = Path(path).name
        download, path = _friendly_subtitle_result(path, resolved, output_format)
        status = status.replace(old_name, Path(path).name)
        if resolved != "auto":
            card = card.replace(
                f"**{output_format.upper()} ready to download**",
                f"**{output_format.upper()} ready to download** · detected **{resolved}**",
            )
    return (
        download,
        rows,
        status,
        path,
        gr.Dropdown(choices=base.LANGUAGE_CHOICES, value=resolved, interactive=True),
        card,
    )


def _translate_with_state(
    mode: str,
    subtitle_path: str,
    source_language: str,
    target_language: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    selected_source = normalize_language_code(source_language)
    if selected_source == "auto":
        selected_source = normalize_language_code(_LAST_SOURCE_LANGUAGE)
    if selected_source == "auto":
        message = (
            "DubLocal could not identify the subtitle source language. Choose it once in From, "
            "or rerun local transcription with Auto detect."
        )
        return None, [], base._error_status(message), "", base.translation_ready_status(
            None, [], source_language, target_language
        )

    output, preview, status, state_path, card = _ORIGINAL_TRANSLATE(
        mode,
        subtitle_path,
        selected_source,
        target_language,
        progress,
    )
    if state_path:
        old_name = Path(state_path).name
        friendly = friendly_subtitle_path(state_path, _LAST_SOURCE_INFO, target_language)
        output = str(friendly)
        state_path = str(friendly)
        status = status.replace(old_name, friendly.name)
    return output, preview, status, state_path, card


def _voice_progress_without_cues(
    subtitle_path,
    *,
    language,
    voice,
    speed=1.0,
    progress_callback=None,
):
    cleaned = prepare_voice_srt(subtitle_path)
    return _ORIGINAL_VOICE_PROGRESS(
        cleaned,
        language=language,
        voice=voice,
        speed=speed,
        progress_callback=progress_callback,
    )


def _generate_voice_ui(*args, **kwargs):
    original = base.generate_voice_track_with_progress
    base.generate_voice_track_with_progress = _voice_progress_without_cues
    try:
        return _ORIGINAL_GENERATE_UI(*args, **kwargs)
    finally:
        base.generate_voice_track_with_progress = original


def _render_m5_ui(
    source_info: dict,
    voice_wav: str | None,
    rights_confirmed: bool,
    language: str | None,
    mode: str,
    container: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    if not rights_confirmed:
        message = "Confirm that you have the right or legal authority to process this media before export."
        base._error_status(message)
        return None, f"⚠ **Export failed** · {message}"
    if not voice_wav:
        message = "Generate the voice track first. M5 mixes that synchronized track with the original soundtrack."
        base._error_status(message)
        return None, f"⚠ **Export failed** · {message}"

    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    try:
        result = render_dubbed_media(
            source_info,
            voice_wav,
            language or "und",
            mode=mode,
            container=container,
            progress_callback=update,
        )
    except Exception as exc:
        message = str(exc)
        base._error_status(message)
        return None, f"⚠ **Export failed** · {message}"

    video_note = "video stream copied · no re-encoding" if result.video_stream_copy else "audio-only source"
    mode_note = (
        "DubLocal mix is the primary/default audio"
        if result.mode == "replace"
        else "original audio kept untouched + DubLocal added as another track"
    )
    timing_note = (
        f"{result.timing_adjusted_segments} voice segment(s) timing-fitted"
        if result.timing_adjusted_segments
        else "voice timing already fit"
    )
    if result.remaining_timing_overflows:
        timing_note += f" · {result.remaining_timing_overflows} long line(s) still exceed the available silence window"
    card = (
        f"✓ **Dubbed media ready · OK** · {result.output_path.name} · {video_note} · "
        f"{mode_note} · {timing_note}"
    )
    return str(result.output_path), card


def build_app() -> gr.Blocks:
    """Build the stable UI and insert v0.5 behavior without leaking test/global mutations."""

    captured: dict[str, Any] = {}
    m5: dict[str, Any] = {}

    original_state = base.gr.State
    original_file = base.gr.File
    original_checkbox = base.gr.Checkbox
    original_dropdown = base.gr.Dropdown
    original_html = base.gr.HTML
    original_accordion = base.gr.Accordion
    original_scan = base._scan_source_ui
    original_extract = base._extract_ui
    original_transcribe = base._transcribe_ui
    original_translate = base._translate_with_state
    original_generate_ui = base._generate_voice_ui

    def state_wrapper(value=None, *args, **kwargs):
        component = original_state(value, *args, **kwargs)
        if "source_state" not in captured and isinstance(value, dict):
            captured["source_state"] = component
        return component

    def file_wrapper(*args, **kwargs):
        component = original_file(*args, **kwargs)
        label = kwargs.get("label") or (args[0] if args and isinstance(args[0], str) else "")
        if label == "Voice-only WAV":
            captured["voice_output"] = component
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
        if label == "Voice language":
            captured["voice_language"] = component
        return component

    def html_wrapper(value=None, *args, **kwargs):
        if isinstance(value, str) and "1 Source</strong> → 2 Subtitles → 3 Translate → 4 Voice-over" in value:
            value = value.replace(
                "1 Source</strong> → 2 Subtitles → 3 Translate → 4 Voice-over.",
                "1 Source</strong> → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export.",
            )
        return original_html(value, *args, **kwargs)

    def accordion_wrapper(*args, **kwargs):
        label = args[0] if args else kwargs.get("label")
        if label == "Results & activity details" and not m5:
            with original_accordion("5 · Export", open=False):
                gr.HTML(
                    '<div class="dl-compact-note">DubLocal fits long voice lines, ducks the original soundtrack under speech, and stream-copies the video whenever possible.</div>'
                )
                with gr.Row():
                    m5["mode"] = gr.Dropdown(
                        label="Audio track",
                        choices=OUTPUT_MODE_CHOICES,
                        value="replace",
                    )
                    m5["container"] = gr.Dropdown(
                        label="Container",
                        choices=CONTAINER_CHOICES,
                        value="mkv",
                    )
                m5["button"] = gr.Button("Create dubbed media", variant="primary")
                m5["status"] = gr.Markdown(
                    "**Waiting** · generate a voice track first.",
                    elem_classes=["dl-stage-status"],
                )
                m5["output"] = gr.File(label="Dubbed media", interactive=False)
                gr.HTML(
                    '<div class="dl-compact-note">Default: replace the primary audio with a DubLocal mix that keeps music/effects underneath. “Add second track” leaves every original audio track untouched. MKV is recommended for maximum compatibility. Video is not re-encoded silently.</div>'
                )
        return original_accordion(*args, **kwargs)

    base.gr.State = state_wrapper
    base.gr.File = file_wrapper
    base.gr.Checkbox = checkbox_wrapper
    base.gr.Dropdown = dropdown_wrapper
    base.gr.HTML = html_wrapper
    base.gr.Accordion = accordion_wrapper
    base._scan_source_ui = _scan_source_ui
    base._extract_ui = _extract_ui
    base._transcribe_ui = _transcribe_ui
    base._translate_with_state = _translate_with_state
    base._generate_voice_ui = _generate_voice_ui
    try:
        demo = previous.build_app()
    finally:
        base.gr.State = original_state
        base.gr.File = original_file
        base.gr.Checkbox = original_checkbox
        base.gr.Dropdown = original_dropdown
        base.gr.HTML = original_html
        base.gr.Accordion = original_accordion
        base._scan_source_ui = original_scan
        base._extract_ui = original_extract
        base._transcribe_ui = original_transcribe
        base._translate_with_state = original_translate
        base._generate_voice_ui = original_generate_ui

    required = {"source_state", "voice_output", "rights", "voice_language"}
    if m5 and required.issubset(captured):
        begin = m5["button"].click(
            fn=lambda: "**Rendering dubbed media…** · timing, audio mix and remux progress/ETA are shown above.",
            outputs=[m5["status"]],
            queue=False,
        )
        begin.then(
            fn=_render_m5_ui,
            inputs=[
                captured["source_state"],
                captured["voice_output"],
                captured["rights"],
                captured["voice_language"],
                m5["mode"],
                m5["container"],
            ],
            outputs=[m5["output"], m5["status"]],
        )

    return demo
