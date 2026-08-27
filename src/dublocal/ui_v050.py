from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import gradio as gr

from . import app as app_module
from . import ui_v042 as previous
from .language_utils import normalize_language_code
from .m5 import CONTAINER_CHOICES, OUTPUT_MODE_CHOICES
from .m51 import VIDEO_QUALITY_CHOICES, render_dubbed_media
from .output_naming import friendly_subtitle_path
from .progress import ProgressEstimator
from .subtitle_export import export_subtitle
from .voice_match import (
    AUTO_VOICE_VALUE,
    auto_default_voice,
    auto_voice_choices,
    resolve_auto_voice_plan,
)
from .voice_text import prepare_voice_srt


base = previous.base
MATRIX_CSS = previous.MATRIX_CSS

_LAST_SOURCE_INFO: dict[str, Any] = {}
_LAST_SOURCE_LANGUAGE = "auto"
_LAST_AUTO_VOICE_SUMMARY = ""

_ORIGINAL_SCAN = base._scan_source_ui
_ORIGINAL_EXTRACT = base._extract_ui
_ORIGINAL_TRANSCRIBE = base._transcribe_ui
_ORIGINAL_TRANSLATE = base._translate_with_state
_ORIGINAL_GENERATE_UI = base._generate_voice_ui
_ORIGINAL_VOICE_PROGRESS = base.generate_voice_track_with_progress
_ORIGINAL_VOICE_DROPDOWN = base._voice_dropdown
_ORIGINAL_SUGGEST_VOICE = base._suggest_voice_controls
_ORIGINAL_PREPARE_KOKORO_SETTINGS = base._prepare_kokoro_settings


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
    global _LAST_SOURCE_LANGUAGE, _LAST_AUTO_VOICE_SUMMARY
    result = _ORIGINAL_SCAN(*args, **kwargs)
    if len(result) >= 3 and isinstance(result[2], dict) and result[2]:
        _remember_source(result[2])
        _LAST_SOURCE_LANGUAGE = "auto"
        _LAST_AUTO_VOICE_SUMMARY = ""
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


def _voice_dropdown_auto(language: str | None):
    choices = auto_voice_choices(language)
    value = auto_default_voice(language)
    return gr.Dropdown(choices=choices, value=value, interactive=bool(choices))


def _suggest_voice_controls_auto(
    timeline_source: str,
    source_language: str,
    target_language: str,
):
    language = source_language if timeline_source == "Source subtitles" else target_language
    suggested = base.suggested_kokoro_language(language)
    if suggested is None:
        return gr.Dropdown(value=None), gr.Dropdown(choices=[], value=None, interactive=False)
    return gr.Dropdown(value=suggested), _voice_dropdown_auto(suggested)


def _prepare_kokoro_settings_auto(language: str, voice: str, *args, **kwargs):
    # Model Manager has no source media to analyse. If Auto is selected there,
    # prepare the normal language default; Main will choose per-segment voices later.
    selected = base.kokoro_default_voice(language) if voice == AUTO_VOICE_VALUE else voice
    return _ORIGINAL_PREPARE_KOKORO_SETTINGS(language, selected, *args, **kwargs)


def _voice_progress_without_cues(
    subtitle_path,
    *,
    language,
    voice,
    speed=1.0,
    progress_callback=None,
):
    global _LAST_AUTO_VOICE_SUMMARY
    cleaned = prepare_voice_srt(subtitle_path)
    if voice != AUTO_VOICE_VALUE:
        _LAST_AUTO_VOICE_SUMMARY = ""
        return _ORIGINAL_VOICE_PROGRESS(
            cleaned,
            language=language,
            voice=voice,
            speed=speed,
            progress_callback=progress_callback,
        )

    def analysis_progress(fraction: float, label: str) -> None:
        if progress_callback:
            progress_callback(0.16 * fraction, label)

    fallback, plan, summary = resolve_auto_voice_plan(
        cleaned,
        _LAST_SOURCE_INFO,
        language,
        progress_callback=analysis_progress,
    )
    _LAST_AUTO_VOICE_SUMMARY = summary

    def tts_progress(fraction: float, label: str) -> None:
        if progress_callback:
            progress_callback(0.16 + 0.84 * fraction, label)

    return _ORIGINAL_VOICE_PROGRESS(
        cleaned,
        language=language,
        voice=fallback,
        speed=speed,
        progress_callback=tts_progress,
        segment_voices=plan,
    )


def _generate_voice_ui(*args, **kwargs):
    original = base.generate_voice_track_with_progress
    base.generate_voice_track_with_progress = _voice_progress_without_cues
    try:
        result = _ORIGINAL_GENERATE_UI(*args, **kwargs)
    finally:
        base.generate_voice_track_with_progress = original
    if _LAST_AUTO_VOICE_SUMMARY and isinstance(result, tuple) and len(result) == 5:
        audio, output, rows, status, card = result
        status = status.replace(
            "[segments]",
            f"[auto voice] {_LAST_AUTO_VOICE_SUMMARY}\n[segments]",
            1,
        )
        card = str(card).replace(AUTO_VOICE_VALUE, f"Auto · {_LAST_AUTO_VOICE_SUMMARY}")
        return audio, output, rows, status, card
    return result


def _render_m5_ui(
    source_info: dict,
    voice_wav: str | None,
    rights_confirmed: bool,
    language: str | None,
    source_subtitle_path: str | None,
    translated_subtitle_path: str | None,
    source_language: str | None,
    translated_language: str | None,
    mode: str,
    container: str,
    video_quality: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    if not rights_confirmed:
        message = "Confirm that you have the right or legal authority to process this media before export."
        base._error_status(message)
        return None, f"⚠ **Export failed** · {message}"
    if not voice_wav:
        message = "Generate the voice track first. Export mixes that synchronized track with the original soundtrack."
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
            video_quality=video_quality,
            source_subtitle_path=source_subtitle_path,
            translated_subtitle_path=translated_subtitle_path,
            source_language=source_language,
            translated_language=translated_language,
            progress_callback=update,
        )
    except Exception as exc:
        message = str(exc)
        base._error_status(message)
        return None, f"⚠ **Export failed** · {message}"

    if result.video_stream_copy:
        video_note = "video stream copied · no re-encoding"
    elif result.source_path.suffix.lower() in {".m4a", ".mp3", ".wav", ".flac", ".aac"}:
        video_note = "audio-only source"
    else:
        video_note = f"video encoded to selected {result.video_quality}p maximum"
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
    subtitle_note = (
        f"{result.embedded_subtitle_tracks} DubLocal subtitle track(s) embedded · selectable in VLC"
        if result.embedded_subtitle_tracks
        else "no generated subtitle track was available to embed"
    )
    card = (
        f"✓ **Dubbed media ready · OK** · {result.output_path.name} · {video_note} · "
        f"{mode_note} · strong source-dialogue suppression · {subtitle_note} · {timing_note}"
    )
    return str(result.output_path), card


def build_app() -> gr.Blocks:
    """Build the stable workflow and layer v0.5.1 refinements onto it."""

    captured: dict[str, Any] = {}
    m5: dict[str, Any] = {}
    blank_states: list[Any] = []

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
    original_voice_dropdown = base._voice_dropdown
    original_suggest_voice = base._suggest_voice_controls
    original_prepare_kokoro_settings = base._prepare_kokoro_settings

    def state_wrapper(value=None, *args, **kwargs):
        component = original_state(value, *args, **kwargs)
        if "source_state" not in captured and isinstance(value, dict):
            captured["source_state"] = component
        elif value == "" and len(blank_states) < 2:
            blank_states.append(component)
            captured["subtitle_path" if len(blank_states) == 1 else "translated_path"] = component
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
        label = kwargs.get("label") or ""
        if label == "Voice":
            kwargs["choices"] = auto_voice_choices("en-US")
            kwargs["value"] = AUTO_VOICE_VALUE
        component = original_dropdown(*args, **kwargs)
        if label == "Voice language":
            captured["voice_language"] = component
        elif label == "From":
            captured["source_language"] = component
        elif label == "To":
            captured["translated_language"] = component
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
                    '<div class="dl-compact-note">Default export keeps local video bit-for-bit, strongly suppresses the original dialogue/singing across subtitle windows, and embeds original + translated subtitles as selectable tracks when available.</div>'
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
                    m5["quality"] = gr.Dropdown(
                        label="Video quality",
                        choices=VIDEO_QUALITY_CHOICES,
                        value="source",
                    )
                m5["button"] = gr.Button("Create dubbed media", variant="primary")
                m5["status"] = gr.Markdown(
                    "**Waiting** · generate a voice track first.",
                    elem_classes=["dl-stage-status"],
                )
                m5["output"] = gr.File(label="Dubbed media", interactive=False)
                gr.HTML(
                    '<div class="dl-compact-note">YouTube: a lower quality selects that source resolution before download, so DubLocal still stream-copies the video. Local files: Original is always no-recode; choosing a lower resolution explicitly enables Apple VideoToolbox H.264 encoding. MKV remains the safest multi-track container.</div>'
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
    base._voice_dropdown = _voice_dropdown_auto
    base._suggest_voice_controls = _suggest_voice_controls_auto
    base._prepare_kokoro_settings = _prepare_kokoro_settings_auto
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
        base._voice_dropdown = original_voice_dropdown
        base._suggest_voice_controls = original_suggest_voice
        base._prepare_kokoro_settings = original_prepare_kokoro_settings

    required = {
        "source_state",
        "subtitle_path",
        "translated_path",
        "voice_output",
        "rights",
        "voice_language",
        "source_language",
        "translated_language",
    }
    if m5 and required.issubset(captured):
        with demo:
            begin = m5["button"].click(
                fn=lambda: "**Rendering dubbed media…** · timing, dialogue suppression, track muxing and ETA are shown above.",
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
                    captured["subtitle_path"],
                    captured["translated_path"],
                    captured["source_language"],
                    captured["translated_language"],
                    m5["mode"],
                    m5["container"],
                    m5["quality"],
                ],
                outputs=[m5["output"], m5["status"]],
            )

    return demo