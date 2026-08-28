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
            '<div class="dl-magic-subtitle">Choose the source and desired result. DubLocal chooses the safest local route and keeps the detailed workflow below for manual control.</div>'
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
            "**Ready** · Magic Flow will explain the subtitle route it selected.",
            elem_classes=["dl-stage-status"],
        )

        with gr.Accordion("Results", open=True):
            with gr.Row():
                source_output = gr.File(label="Source subtitles", interactive=False)
                translated_output = gr.File(label="Translated subtitles", interactive=False)
            with gr.Row():
                voice_output = gr.File(label="Voice-only WAV", interactive=False)
                media_output = gr.File(label="Output media", interactive=False)

        begin = run.click(
            fn=lambda: "**Running Magic Flow…** · source analysis, route selection and ETA will appear above.",
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


def build_app() -> gr.Blocks:
    """Add a commercial-friendly Magic Flow while preserving the existing detailed workflow."""

    original_html = base.gr.HTML
    original_translate = detailed._translate_with_state
    inserted = {"magic": False}

    def html_wrapper(value=None, *args, **kwargs):
        if (
            not inserted["magic"]
            and isinstance(value, str)
            and "1 Source</strong>" in value
        ):
            inserted["magic"] = True
            _build_magic_panel(original_html)
            value = (
                '<div class="dl-flow"><strong>Detailed workflow</strong> · '
                'Use the stages below when you want manual control over source subtitles, models, translation, voice and export.</div>'
            )
        return original_html(value, *args, **kwargs)

    base.gr.HTML = html_wrapper
    detailed._translate_with_state = _translate_with_state_auto_safe
    try:
        return previous.build_app()
    finally:
        base.gr.HTML = original_html
        detailed._translate_with_state = original_translate
