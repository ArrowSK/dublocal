from __future__ import annotations

from pathlib import Path
from typing import Any

import gradio as gr

from . import ui_v050 as detailed
from . import ui_v053 as previous
from .language_utils import normalize_language_code
from .m51 import VIDEO_QUALITY_CHOICES
from .m5 import CONTAINER_CHOICES
from .magic_flow import (
    MAGIC_SUBTITLE_POLICY_CHOICES,
    MAGIC_TASK_CHOICES,
    run_magic_flow,
)
from .output_naming import friendly_subtitle_path
from .progress import ProgressEstimator


base = detailed.base
MATRIX_CSS = previous.MATRIX_CSS + r"""
.dl-magic-shell {
  border: 1px solid rgba(66, 239, 131, 0.58) !important;
  border-radius: 12px !important;
  padding: 14px !important;
  margin: 8px 0 18px 0 !important;
  background: linear-gradient(180deg, rgba(9, 28, 17, 0.72), rgba(7, 16, 10, 0.72)) !important;
}
.dl-magic-title {
  color: var(--dl-green) !important;
  font-weight: 700 !important;
  font-size: 16px !important;
  margin-bottom: 2px !important;
}
.dl-magic-subtitle {
  color: var(--dl-muted) !important;
  font-size: 12px !important;
  margin-bottom: 8px !important;
}
.dl-main-mode-note {
  color: var(--dl-muted) !important;
  font-size: 12px !important;
  margin: 2px 0 12px 0 !important;
}
.dl-magic-shell progress,
.dl-magic-shell [role="progressbar"] {
  accent-color: var(--dl-green) !important;
}
"""


_ORIGINAL_DETAILED_TRANSLATE = detailed._translate_with_state


def _translate_with_state_auto_safe(
    mode: str,
    subtitle_path: str,
    source_language: str,
    target_language: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    """Resolve detected transcription language first; let contextual Auto detect otherwise."""

    selected_source = normalize_language_code(source_language)
    if selected_source == "auto":
        cached = normalize_language_code(detailed._LAST_SOURCE_LANGUAGE)
        if cached != "auto":
            selected_source = cached
        elif mode == "contextual":
            # Contextual translation has its own lightweight language-ID prompt and can
            # safely consume Auto. This is the important fix: never reject Auto and then
            # tell the user to choose Auto again.
            selected_source = "auto"
        else:
            message = (
                "Legacy OPUS translation needs a known source language. Use Contextual quality with From = Auto, "
                "or choose the detected language manually."
            )
            return None, [], base._error_status(message), "", base.translation_ready_status(
                None, [], source_language, target_language
            )

    output, preview, status, state_path, card = detailed._ORIGINAL_TRANSLATE(
        mode,
        subtitle_path,
        selected_source,
        target_language,
        progress,
    )
    if state_path:
        old_name = Path(state_path).name
        friendly = friendly_subtitle_path(state_path, detailed._LAST_SOURCE_INFO, target_language)
        output = str(friendly)
        state_path = str(friendly)
        status = status.replace(old_name, friendly.name)
    return output, preview, status, state_path, card


def _run_magic_ui(
    source_type: str,
    youtube_url: str,
    local_file: str | None,
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
        result = run_magic_flow(
            source_type=source_type,
            youtube_url=youtube_url,
            local_file=local_file,
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
        message = str(exc)
        base._error_status(message)
        return None, None, None, None, f"⚠ **Magic Flow failed** · {message}"

    status = (
        f"✓ **Magic Flow complete · OK** · {result.decision} · "
        f"source language **{result.source_language}** · output **{result.target_language}**"
    )
    return (
        str(result.source_subtitle) if result.source_subtitle else None,
        str(result.translated_subtitle) if result.translated_subtitle else None,
        str(result.voice_wav) if result.voice_wav else None,
        str(result.media_output) if result.media_output else None,
        status,
    )


def _build_magic_panel(original_html) -> None:
    with gr.Group(elem_classes=["dl-magic-shell"]):
        original_html('<div class="dl-magic-title">Magic Flow</div>')
        original_html(
            '<div class="dl-magic-subtitle">Choose the source and desired result. DubLocal chooses the safest local route automatically. Most users only need this tab.</div>'
        )

        source_type = gr.Radio(
            choices=["YouTube", "Local file"],
            value="YouTube",
            label="Source",
        )
        youtube_url = gr.Textbox(
            label="YouTube URL",
            placeholder="https://www.youtube.com/watch?v=...",
        )
        local_file = gr.File(
            label="Local media",
            file_types=["video", "audio"],
            type="filepath",
            visible=False,
        )
        source_type.change(
            fn=base._toggle_source,
            inputs=[source_type],
            outputs=[youtube_url, local_file],
            queue=False,
        )

        rights = gr.Checkbox(
            label="I have the right or legal authority to process this media",
            value=False,
        )

        with gr.Row():
            target_language = gr.Dropdown(
                label="Output language",
                choices=base.TARGET_LANGUAGE_CHOICES,
                value="en",
                interactive=True,
            )
            tasks = gr.CheckboxGroup(
                label="Create",
                choices=MAGIC_TASK_CHOICES,
                value=["subtitles", "translate", "voice", "media"],
            )

        with gr.Accordion("More options", open=False):
            original_html(
                '<div class="dl-compact-note">Magic defaults are reversible and hardware-safe. Change these only when you need more control.</div>'
            )
            subtitle_policy = gr.Dropdown(
                label="Subtitle source",
                choices=MAGIC_SUBTITLE_POLICY_CHOICES,
                value="auto",
            )
            keep_original_audio = gr.Checkbox(
                label="Keep original audio as a separate selectable track",
                value=True,
            )
            with gr.Row():
                container = gr.Dropdown(
                    label="Output format",
                    choices=CONTAINER_CHOICES,
                    value="mkv",
                )
                quality = gr.Dropdown(
                    label="Video quality",
                    choices=VIDEO_QUALITY_CHOICES,
                    value="source",
                )
            original_html(
                '<div class="dl-compact-note">Recommended defaults: MKV, original/best video quality, original audio retained as a separate track. Local Original uses stream-copy and does not re-encode video.</div>'
            )

        run = gr.Button("Run Magic Flow", variant="primary")
        status = gr.Markdown(
            "**Ready** · Magic Flow will explain the route it selected.",
            elem_classes=["dl-stage-status"],
        )

        # Keep four output components out of sight while processing. The status card
        # above is the single source of progress; users open Results once outputs exist.
        with gr.Accordion("Results", open=False):
            with gr.Row():
                source_output = gr.File(label="Source subtitles", interactive=False)
                translated_output = gr.File(label="Translated subtitles", interactive=False)
            with gr.Row():
                voice_output = gr.File(label="Voice-only WAV", interactive=False)
                media_output = gr.File(label="Output media", interactive=False)

        begin = run.click(
            fn=lambda: "**Running Magic Flow…** · source analysis, route selection and ETA are shown here.",
            outputs=[status],
            queue=False,
        )
        begin.then(
            fn=_run_magic_ui,
            inputs=[
                source_type,
                youtube_url,
                local_file,
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
                status,
            ],
        )


class _MainTabContext:
    """Turn the existing Main tab into Simple/Advanced without rebuilding Advanced.

    The stable UI already creates the entire manual workflow inside `with gr.Tab("Main")`.
    This context wrapper opens a nested Tabs container, renders Magic Flow in the first
    tab, then leaves Advanced open while the existing builder creates its components.
    That preserves the established event wiring and avoids duplicating the manual UI.
    """

    def __init__(self, original_tab, original_tabs, original_html, args, kwargs):
        self._original_tab = original_tab
        self._original_tabs = original_tabs
        self._original_html = original_html
        self._args = args
        self._kwargs = kwargs
        self._main = None
        self._inner_tabs = None
        self._advanced = None

    def __enter__(self):
        self._main = self._original_tab(*self._args, **self._kwargs)
        result = self._main.__enter__()

        self._inner_tabs = self._original_tabs()
        self._inner_tabs.__enter__()

        simple = self._original_tab("Simple")
        simple.__enter__()
        try:
            self._original_html(
                '<div class="dl-main-mode-note">Simple is the default for normal use. Switch to Advanced only when you need manual control of individual stages.</div>'
            )
            _build_magic_panel(self._original_html)
        finally:
            simple.__exit__(None, None, None)

        self._advanced = self._original_tab("Advanced")
        self._advanced.__enter__()
        return result

    def __exit__(self, exc_type, exc, tb):
        suppress = False
        if self._advanced is not None:
            suppress = bool(self._advanced.__exit__(exc_type, exc, tb)) or suppress
        if self._inner_tabs is not None:
            suppress = bool(self._inner_tabs.__exit__(exc_type, exc, tb)) or suppress
        if self._main is not None:
            suppress = bool(self._main.__exit__(exc_type, exc, tb)) or suppress
        return suppress


def build_app() -> gr.Blocks:
    """Expose Simple and Advanced as true subtabs under Main."""

    original_html = base.gr.HTML
    original_tab = base.gr.Tab
    original_tabs = base.gr.Tabs
    original_translate = detailed._translate_with_state

    def tab_wrapper(*args, **kwargs):
        label = args[0] if args else kwargs.get("label")
        if label == "Main":
            return _MainTabContext(
                original_tab,
                original_tabs,
                original_html,
                args,
                kwargs,
            )
        return original_tab(*args, **kwargs)

    def html_wrapper(value=None, *args, **kwargs):
        if isinstance(value, str) and "1 Source</strong>" in value:
            value = (
                '<div class="dl-flow"><strong>Advanced workflow</strong> · '
                'Use these stages when you want manual control over source subtitles, models, translation, voice and export.</div>'
            )
        return original_html(value, *args, **kwargs)

    base.gr.Tab = tab_wrapper
    base.gr.HTML = html_wrapper
    detailed._translate_with_state = _translate_with_state_auto_safe
    try:
        return previous.build_app()
    finally:
        base.gr.Tab = original_tab
        base.gr.HTML = original_html
        detailed._translate_with_state = original_translate
