from __future__ import annotations

from pathlib import Path
from typing import Any

import gradio as gr

from . import magic_flow
from . import ui_v050 as detailed
from . import ui_v053 as previous
from .adaptive_audio import (
    MIX_STRATEGY_CHOICES,
    advanced_mix_preference,
    audio_mix_status,
    last_mix_summary,
    prepare_separation_ui,
    render_magic_dubbed_media,
    set_advanced_mix_preference,
)
from .batch_flow import download_groups, queue_rows, run_magic_queue
from .language_utils import normalize_language_code
from .m51 import VIDEO_QUALITY_CHOICES
from .m5 import CONTAINER_CHOICES
from .magic_flow import MAGIC_LOCAL_TRANSCRIPTION_CHOICES, MAGIC_SUBTITLE_POLICY_CHOICES
from .model_setup import (
    mark_first_run_skipped,
    model_setup_state,
    model_setup_summary,
    prepare_recommended_models,
)
from .normal_update import update_dublocal_ui, updater_idle_status
from .output_naming import friendly_subtitle_path
from .progress import ProgressEstimator
from .transcription import whisper_model_path
from .tts_provider_refinement import (
    prepare_registered_provider_ui,
    register_custom_provider_ui,
    registered_provider_choices,
)
from .tts_provider_registry import provider_status_text


base = detailed.base

# Magic Flow keeps four user-facing outputs. The media choice already supports a
# subtitles-only package when Translate and Voice-over are off, so make that explicit
# without adding another control.
MAGIC_TASK_CHOICES = [
    ("Subtitles", "subtitles"),
    ("Translate", "translate"),
    ("Voice-over", "voice"),
    ("Media file · original + subtitles if Translate/Voice are off", "media"),
]

_MAGIC_CSS = r"""
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

# Product-level Gradio theme. Keep error states red; only neutral/accent surfaces are
# normalized into DubLocal's dark-green palette.
THEME_CONSISTENCY_CSS = r"""
.gradio-container {
  --body-background-fill: var(--dl-bg) !important;
  --body-background-fill-dark: var(--dl-bg) !important;
  --body-text-color: var(--dl-text) !important;
  --body-text-color-dark: var(--dl-text) !important;
  --body-text-color-subdued: var(--dl-muted) !important;
  --body-text-color-subdued-dark: var(--dl-muted) !important;

  --background-fill-primary: #0b1510 !important;
  --background-fill-primary-dark: #0b1510 !important;
  --background-fill-secondary: #101b15 !important;
  --background-fill-secondary-dark: #101b15 !important;

  --border-color-primary: rgba(43, 108, 66, 0.72) !important;
  --border-color-primary-dark: rgba(43, 108, 66, 0.72) !important;
  --border-color-accent: var(--dl-green) !important;
  --border-color-accent-dark: var(--dl-green) !important;
  --border-color-accent-subdued: var(--dl-border) !important;
  --border-color-accent-subdued-dark: var(--dl-border) !important;
  --color-accent: var(--dl-green) !important;
  --color-accent-soft: rgba(66, 239, 131, 0.12) !important;
  --color-accent-soft-dark: rgba(66, 239, 131, 0.12) !important;

  --block-background-fill: #0b1510 !important;
  --block-background-fill-dark: #0b1510 !important;
  --block-border-color: rgba(43, 108, 66, 0.62) !important;
  --block-border-color-dark: rgba(43, 108, 66, 0.62) !important;
  --block-label-background-fill: #101b15 !important;
  --block-label-background-fill-dark: #101b15 !important;
  --block-label-border-color: rgba(43, 108, 66, 0.62) !important;
  --block-label-border-color-dark: rgba(43, 108, 66, 0.62) !important;
  --block-label-text-color: var(--dl-text) !important;
  --block-label-text-color-dark: var(--dl-text) !important;
  --block-title-text-color: var(--dl-text) !important;
  --block-title-text-color-dark: var(--dl-text) !important;
  --block-info-text-color: var(--dl-muted) !important;
  --block-info-text-color-dark: var(--dl-muted) !important;

  --panel-background-fill: #0b1510 !important;
  --panel-background-fill-dark: #0b1510 !important;
  --panel-border-color: rgba(43, 108, 66, 0.62) !important;
  --panel-border-color-dark: rgba(43, 108, 66, 0.62) !important;
  --accordion-text-color: var(--dl-text) !important;
  --accordion-text-color-dark: var(--dl-text) !important;

  --input-background-fill: #0d1711 !important;
  --input-background-fill-dark: #0d1711 !important;
  --input-background-fill-focus: #101d15 !important;
  --input-background-fill-focus-dark: #101d15 !important;
  --input-background-fill-hover: #101d15 !important;
  --input-background-fill-hover-dark: #101d15 !important;
  --input-border-color: rgba(43, 108, 66, 0.72) !important;
  --input-border-color-dark: rgba(43, 108, 66, 0.72) !important;
  --input-border-color-focus: var(--dl-green) !important;
  --input-border-color-focus-dark: var(--dl-green) !important;
  --input-border-color-hover: rgba(66, 239, 131, 0.72) !important;
  --input-border-color-hover-dark: rgba(66, 239, 131, 0.72) !important;
  --input-border-width: 1px !important;
  --input-border-width-dark: 1px !important;
  --input-placeholder-color: var(--dl-muted) !important;
  --input-placeholder-color-dark: var(--dl-muted) !important;

  --checkbox-background-color: #0d1711 !important;
  --checkbox-background-color-dark: #0d1711 !important;
  --checkbox-background-color-hover: #101d15 !important;
  --checkbox-background-color-hover-dark: #101d15 !important;
  --checkbox-background-color-selected: var(--dl-green) !important;
  --checkbox-background-color-selected-dark: var(--dl-green) !important;
  --checkbox-border-color: rgba(43, 108, 66, 0.72) !important;
  --checkbox-border-color-dark: rgba(43, 108, 66, 0.72) !important;
  --checkbox-border-color-focus: var(--dl-green) !important;
  --checkbox-border-color-focus-dark: var(--dl-green) !important;
  --checkbox-border-color-hover: rgba(66, 239, 131, 0.72) !important;
  --checkbox-border-color-hover-dark: rgba(66, 239, 131, 0.72) !important;
  --checkbox-border-color-selected: var(--dl-green) !important;
  --checkbox-border-color-selected-dark: var(--dl-green) !important;
  --checkbox-label-background-fill: #101b15 !important;
  --checkbox-label-background-fill-dark: #101b15 !important;
  --checkbox-label-background-fill-hover: #16271d !important;
  --checkbox-label-background-fill-hover-dark: #16271d !important;
  --checkbox-label-background-fill-selected: rgba(66, 239, 131, 0.12) !important;
  --checkbox-label-background-fill-selected-dark: rgba(66, 239, 131, 0.12) !important;
  --checkbox-label-border-color: var(--dl-border) !important;
  --checkbox-label-border-color-dark: var(--dl-border) !important;
  --checkbox-label-border-color-hover: rgba(66, 239, 131, 0.72) !important;
  --checkbox-label-border-color-hover-dark: rgba(66, 239, 131, 0.72) !important;
  --checkbox-label-border-color-selected: rgba(66, 239, 131, 0.72) !important;
  --checkbox-label-border-color-selected-dark: rgba(66, 239, 131, 0.72) !important;
  --checkbox-label-text-color: var(--dl-text) !important;
  --checkbox-label-text-color-dark: var(--dl-text) !important;
  --checkbox-label-text-color-selected: var(--dl-text) !important;
  --checkbox-label-text-color-selected-dark: var(--dl-text) !important;

  --loader-color: var(--dl-green) !important;
  --loader-color-dark: var(--dl-green) !important;
  --slider-color: var(--dl-green) !important;
  --slider-color-dark: var(--dl-green) !important;
  --stat-background-fill: var(--dl-green) !important;
  --stat-background-fill-dark: var(--dl-green) !important;

  --button-primary-background-fill: var(--dl-green) !important;
  --button-primary-background-fill-dark: var(--dl-green) !important;
  --button-primary-background-fill-hover: var(--dl-green-soft) !important;
  --button-primary-background-fill-hover-dark: var(--dl-green-soft) !important;
  --button-primary-border-color: var(--dl-green) !important;
  --button-primary-border-color-dark: var(--dl-green) !important;
  --button-primary-border-color-hover: var(--dl-green-soft) !important;
  --button-primary-border-color-hover-dark: var(--dl-green-soft) !important;
  --button-primary-text-color: #041008 !important;
  --button-primary-text-color-dark: #041008 !important;
  --button-primary-text-color-hover: #041008 !important;
  --button-primary-text-color-hover-dark: #041008 !important;

  --button-secondary-background-fill: #101b15 !important;
  --button-secondary-background-fill-dark: #101b15 !important;
  --button-secondary-background-fill-hover: #16271d !important;
  --button-secondary-background-fill-hover-dark: #16271d !important;
  --button-secondary-border-color: var(--dl-border) !important;
  --button-secondary-border-color-dark: var(--dl-border) !important;
  --button-secondary-border-color-hover: rgba(66, 239, 131, 0.72) !important;
  --button-secondary-border-color-hover-dark: rgba(66, 239, 131, 0.72) !important;
  --button-secondary-text-color: var(--dl-green-soft) !important;
  --button-secondary-text-color-dark: var(--dl-green-soft) !important;
  --button-secondary-text-color-hover: var(--dl-text) !important;
  --button-secondary-text-color-hover-dark: var(--dl-text) !important;

  --table-text-color: var(--dl-text) !important;
  --table-text-color-dark: var(--dl-text) !important;
  --table-border-color: rgba(43, 108, 66, 0.62) !important;
  --table-border-color-dark: rgba(43, 108, 66, 0.62) !important;
  --table-even-background-fill: #0b1510 !important;
  --table-even-background-fill-dark: #0b1510 !important;
  --table-odd-background-fill: #101b15 !important;
  --table-odd-background-fill-dark: #101b15 !important;
  --table-row-focus: rgba(66, 239, 131, 0.12) !important;
  --table-row-focus-dark: rgba(66, 239, 131, 0.12) !important;

  --link-text-color: var(--dl-green-soft) !important;
  --link-text-color-dark: var(--dl-green-soft) !important;
  --link-text-color-active: var(--dl-green) !important;
  --link-text-color-active-dark: var(--dl-green) !important;
  --link-text-color-hover: var(--dl-green) !important;
  --link-text-color-hover-dark: var(--dl-green) !important;
  --link-text-color-visited: var(--dl-green-soft) !important;
  --link-text-color-visited-dark: var(--dl-green-soft) !important;
  --code-background-fill: #07100a !important;
  --code-background-fill-dark: #07100a !important;
}

.gradio-container [data-testid="status-tracker"] .progress-bar-wrap {
  border-color: var(--dl-border) !important;
  background: #07100a !important;
}
.gradio-container [data-testid="status-tracker"] .progress-bar,
.gradio-container .progress-bar {
  background-color: var(--dl-green) !important;
}
.gradio-container [data-testid="status-tracker"] .progress-level-inner,
.gradio-container [data-testid="status-tracker"] .progress-text,
.gradio-container [data-testid="status-tracker"] .meta-text,
.gradio-container [data-testid="status-tracker"] .meta-text-center {
  color: var(--dl-text) !important;
}
"""

_QUEUE_UPDATE_CSS = r"""
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

_ALIGNMENT_MODEL_CSS = r"""
.dl-magic-shell {
  padding: 18px !important;
}
.dl-magic-shell > .form,
.dl-magic-shell > .wrap {
  padding: 0 !important;
  margin: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.dl-magic-shell > * {
  box-sizing: border-box !important;
  margin-left: 0 !important;
  margin-right: 0 !important;
  max-width: 100% !important;
}
.dl-magic-shell .block:has(.dl-magic-title),
.dl-magic-shell .block:has(.dl-magic-subtitle),
.dl-magic-shell .block:has(.dl-compact-note),
.dl-magic-shell .dl-queue-note {
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.dl-magic-shell .block:has(.dl-magic-title),
.dl-magic-shell .block:has(.dl-magic-subtitle) {
  padding: 0 !important;
  margin: 0 !important;
  min-height: 0 !important;
}
.dl-magic-shell .dl-queue-note {
  padding: 2px 0 4px 0 !important;
  margin: 0 !important;
  min-height: 0 !important;
}
.dl-magic-shell .dl-stage-status {
  margin-left: 0 !important;
  margin-right: 0 !important;
  width: 100% !important;
}
.dl-magic-shell button.primary {
  width: 100% !important;
}

.dl-model-setup-card {
  border: 1px solid rgba(66, 239, 131, 0.50) !important;
  border-radius: 12px !important;
  padding: 18px !important;
  margin: 4px 0 18px 0 !important;
  background: rgba(7, 18, 11, 0.76) !important;
  box-shadow: none !important;
}
.dl-model-setup-card > .form,
.dl-model-setup-card > .wrap {
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.dl-model-setup-title {
  color: var(--dl-green) !important;
  font-size: 17px !important;
  font-weight: 700 !important;
  margin: 0 0 4px 0 !important;
}
.dl-model-setup-copy {
  color: var(--dl-muted) !important;
  font-size: 12px !important;
  margin: 0 0 10px 0 !important;
}
.dl-model-setup-summary {
  border: 0 !important;
  background: transparent !important;
  padding: 0 !important;
  margin: 2px 0 10px 0 !important;
  box-shadow: none !important;
}
.dl-model-setup-actions {
  align-items: stretch !important;
}
.dl-model-setup-actions button {
  min-height: 40px !important;
}
"""

MATRIX_CSS = (
    previous.MATRIX_CSS
    + _MAGIC_CSS
    + THEME_CONSISTENCY_CSS
    + _QUEUE_UPDATE_CSS
    + _ALIGNMENT_MODEL_CSS
)

# Magic Flow is always automatic. Advanced can override its own export strategy.
magic_flow.render_dubbed_media = render_magic_dubbed_media

_EXAMPLE_MANIFEST = """{
  "schema_version": 1,
  "id": "my-russian-kokoro",
  "label": "My vetted Russian Kokoro mirror",
  "language": "ru",
  "language_label": "Russian",
  "backend": "kokoro-local",
  "frontend": "russian-v2",
  "source": {
    "type": "local",
    "path": "/Users/me/Models/my-russian-kokoro"
  },
  "license": {
    "id": "OpenRAIL",
    "commercial_use": true,
    "redistribution": "not-bundled",
    "source": "model-card-or-license-location",
    "attribution": "required attribution text"
  },
  "config_file": "kokoro-config.json",
  "voices": [
    {
      "id": "rf_sveta",
      "label": "Sveta · female",
      "gender": "female",
      "model_file": "kokoro-ru-v2-base.pth",
      "voice_file": "voices/sveta.pt"
    }
  ],
  "default_voice": "rf_sveta",
  "preferred": true
}"""

_ORIGINAL_RENDER_UI = detailed._render_m5_ui


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


def _render_with_mix_summary(*args, **kwargs):
    result = _ORIGINAL_RENDER_UI(*args, **kwargs)
    if not isinstance(result, tuple) or len(result) != 2:
        return result
    output, card = result
    return output, str(card).replace("strong source-dialogue suppression", last_mix_summary())


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


def _default_local_transcription_policy() -> str:
    try:
        if whisper_model_path("large-v3-turbo-q5_0").is_file():
            return "local-best"
    except Exception:
        pass
    return "local-fast"


def _toggle_local_transcription_quality(subtitle_policy: str):
    return gr.Dropdown(visible=subtitle_policy == "local")


def _run_batch_magic_ui(
    source_type: str,
    youtube_url: str,
    local_files: Any,
    rights_confirmed: bool,
    target_language: str,
    tasks: list[str] | None,
    subtitle_policy: str,
    local_transcription_policy: str,
    keep_original_audio_track: bool,
    container: str,
    video_quality: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    effective_subtitle_policy = (
        local_transcription_policy
        if subtitle_policy == "local" and local_transcription_policy in {"local-fast", "local-best"}
        else subtitle_policy
    )

    try:
        result = run_magic_queue(
            source_type=source_type,
            youtube_url=youtube_url,
            local_files=local_files,
            rights_confirmed=rights_confirmed,
            target_language=target_language,
            tasks=tasks,
            subtitle_policy=effective_subtitle_policy,
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
    location = (
        "finished outputs were also saved next to each original local file"
        if source_type == "Local file"
        else "finished outputs were also saved in Downloads/DubLocal"
    )
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
                '<div class="dl-compact-note">The same settings apply to every queued item. A failed item does not discard successful items or stop the rest of the queue.</div>'
            )
            subtitle_policy = gr.Dropdown(
                label="Subtitle source",
                choices=MAGIC_SUBTITLE_POLICY_CHOICES,
                value="auto",
            )
            local_transcription_policy = gr.Dropdown(
                label="Local transcription quality",
                choices=MAGIC_LOCAL_TRANSCRIPTION_CHOICES,
                value=_default_local_transcription_policy(),
                visible=False,
                info="FAST uses Base for speed. BEST uses Accurate Large v3 Turbo Q5 for maximum transcription quality.",
            )
            subtitle_policy.change(
                fn=_toggle_local_transcription_quality,
                inputs=[subtitle_policy],
                outputs=[local_transcription_policy],
                queue=False,
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
                local_transcription_policy,
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


def _setup_progress(progress: gr.Progress):
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    return update


def _prepare_setup_ui(progress: gr.Progress = gr.Progress(track_tqdm=True)):
    try:
        summary = prepare_recommended_models(progress_callback=_setup_progress(progress))
        try:
            gr.Info("Recommended DubLocal models are ready.")
        except Exception:
            pass
        return summary, gr.Column(visible=False)
    except Exception as exc:
        return (
            f"### Setup needs attention\n{exc}\n\nAnything already prepared was kept. You can run the wizard again.",
            gr.Column(visible=True),
        )


def _skip_first_run_ui():
    mark_first_run_skipped()
    return gr.Column(visible=False)


def _build_model_setup_card(*, first_run: bool) -> gr.Column:
    state = model_setup_state()
    panel = gr.Column(
        visible=(state.first_run_pending if first_run else True),
        elem_classes=["dl-model-setup-card"],
    )
    with panel:
        gr.HTML(
            '<div class="dl-model-setup-title">'
            + ("Welcome · model setup" if first_run else "Model Setup")
            + "</div>"
        )
        gr.HTML(
            '<div class="dl-model-setup-copy">'
            + (
                "DubLocal has chosen a practical local model set for this Mac. One action prepares subtitles, contextual translation and voice-over; nothing is downloaded until you approve it."
                if first_run
                else "Use the same simple hardware-aware setup at any time. It prepares or repairs only the models DubLocal recommends for this Mac. Detailed per-model controls remain under Model Manager."
            )
            + "</div>"
        )
        status = gr.Markdown(model_setup_summary(), elem_classes=["dl-model-setup-summary"])
        with gr.Row(elem_classes=["dl-model-setup-actions"]):
            prepare = gr.Button(
                "Set up recommended models" if first_run else "Prepare / repair recommended setup",
                variant="primary",
            )
            skip = gr.Button("Skip for now", variant="secondary") if first_run else None

        begin = prepare.click(
            fn=lambda: "### Preparing recommended models…\nDubLocal will show the active download/preparation stage in the progress bar.",
            outputs=[status],
            queue=False,
        )
        begin.then(fn=_prepare_setup_ui, outputs=[status, panel])
        if skip is not None:
            skip.click(fn=_skip_first_run_ui, outputs=[panel], queue=False)
    return panel


def _register_and_refresh(manifest_text: str):
    status, action = register_custom_provider_ui(manifest_text)
    choices = registered_provider_choices()
    value = choices[-1][1] if choices else None
    return status, action, gr.Dropdown(choices=choices, value=value, interactive=bool(choices))


def _build_audio_advanced_controls(original_html) -> None:
    original_html(
        '<div class="dl-compact-note"><strong>Audio mix</strong> · Auto keeps the fast dialogue path for normal material and uses prepared vocal separation only when music is strongly indicated.</div>'
    )
    strategy = gr.Dropdown(
        label="Audio mix strategy",
        choices=MIX_STRATEGY_CHOICES,
        value=advanced_mix_preference(),
        interactive=True,
    )
    status = gr.Markdown(audio_mix_status(), elem_classes=["console"])
    strategy.change(
        fn=set_advanced_mix_preference,
        inputs=[strategy],
        outputs=[status],
        queue=False,
    )


def _build_settings_injections(original_html) -> None:
    with gr.Accordion("Vocal separation · music-aware dubbing", open=False):
        status = gr.Markdown(audio_mix_status(), elem_classes=["console"])
        prepare = gr.Button("Prepare vocal separation", variant="secondary")
        original_html(
            '<div class="dl-note">Optional Demucs vocal separation runs locally in an isolated runtime. The compatibility baseline is CPU inference with chunk size selected from available memory, so the same feature can run on 8 GB M1-class Macs and larger M-series machines. Simple mode never requires this model to finish a dub.</div>'
        )
        prepare.click(fn=prepare_separation_ui, outputs=[status])

    with gr.Accordion("Local TTS providers · Russian & custom models", open=False):
        status = gr.Markdown(provider_status_text(), elem_classes=["console"])
        action = gr.Markdown(
            "```text\n[provider] choose a provider to prepare, or register a custom manifest below\n```",
            elem_classes=["console"],
        )
        original_html(
            '<div class="dl-note"><strong>Russian:</strong> DubLocal uses a vetted third-party Kokoro-RU provider, not official Hexgrad Russian support. Preparing it stores a persistent local snapshot and exact revision receipt; normal generation then uses local files even if that model fork later disappears. <strong>Ukrainian:</strong> no built-in provider is enabled yet pending a stronger rights/provenance review.</div>'
        )
        choices = registered_provider_choices()
        provider = gr.Dropdown(
            label="Registered provider",
            choices=choices,
            value=choices[0][1] if choices else None,
            interactive=bool(choices),
        )
        prepare = gr.Button("Prepare selected provider", variant="secondary")
        prepare.click(fn=prepare_registered_provider_ui, inputs=[provider], outputs=[status, action])

        original_html(
            '<div class="dl-compact-note"><strong>Custom models are manifests, not plugins.</strong> DubLocal accepts only allowlisted local Kokoro-compatible frontends and model/voice/config files. Python modules, scripts, shell commands and arbitrary entrypoints are rejected. Remote manifests must pin an immutable commit revision and SHA-256 assets; local mirrors are also supported.</div>'
        )
        manifest = gr.Code(
            label="Custom provider manifest · JSON",
            value=_EXAMPLE_MANIFEST,
            language="json",
            lines=18,
        )
        register = gr.Button("Validate & register custom provider", variant="secondary")
        register.click(
            fn=_register_and_refresh,
            inputs=[manifest],
            outputs=[status, action, provider],
        )


class _MainTabContext:
    """Expose Simple and Advanced as true subtabs without rebuilding the detailed workflow."""

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
            if model_setup_state().first_run_pending:
                _build_model_setup_card(first_run=True)
            _build_batch_magic_panel(self._original_html)
        finally:
            simple.__exit__(None, None, None)

        self._advanced = self._original_tab("Advanced")
        self._advanced.__enter__()
        _build_audio_advanced_controls(self._original_html)
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


class _SettingsTabContext:
    def __init__(self, original_tab, original_html, args, kwargs):
        self._original_tab = original_tab
        self._original_html = original_html
        self._args = args
        self._kwargs = kwargs
        self._context = None

    def __enter__(self):
        self._context = self._original_tab(*self._args, **self._kwargs)
        result = self._context.__enter__()
        _build_settings_injections(self._original_html)
        return result

    def __exit__(self, exc_type, exc, tb):
        if self._context is None:
            return False
        return self._context.__exit__(exc_type, exc, tb)


class _ModelManagerTabsContext:
    def __init__(self, original_tab, args, kwargs):
        self._original_tab = original_tab
        self._args = args
        self._kwargs = kwargs
        self._advanced = None

    def __enter__(self):
        with self._original_tab("Model Setup"):
            _build_model_setup_card(first_run=False)
        self._advanced = self._original_tab(*self._args, **self._kwargs)
        return self._advanced.__enter__()

    def __exit__(self, exc_type, exc, tb):
        if self._advanced is None:
            return False
        return self._advanced.__exit__(exc_type, exc, tb)


class _UpdatesTabContext:
    """Replace developer-style updater controls with one normal application action."""

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

        # The detailed builder still creates/wires the legacy controls. Keep them alive
        # but invisible until that older settings implementation is consolidated too.
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
    """Build the current production-facing UI from one active product layer.

    The remaining versioned modules belong to the older detailed-workflow builder and
    are intentionally left for the next consolidation pass. No v0.60-v0.64 overlay is
    required by the launcher after this module.
    """

    original_tab = gr.Tab
    original_tabs = gr.Tabs
    original_html = gr.HTML
    original_translate = detailed._translate_with_state
    original_render = detailed._render_m5_ui

    def tab_wrapper(*args: Any, **kwargs: Any):
        label = args[0] if args else kwargs.get("label")
        if label == "Main":
            return _MainTabContext(original_tab, original_tabs, original_html, args, kwargs)
        if label == "Settings":
            return _SettingsTabContext(original_tab, original_html, args, kwargs)
        if label == "Model Manager":
            return _ModelManagerTabsContext(original_tab, args, kwargs)
        if label == "Updates":
            return _UpdatesTabContext(original_tab, args, kwargs)
        return original_tab(*args, **kwargs)

    def html_wrapper(value=None, *args, **kwargs):
        if isinstance(value, str) and "1 Source</strong>" in value:
            value = (
                '<div class="dl-flow"><strong>Advanced workflow</strong> · '
                'Use these stages when you want manual control over source subtitles, models, translation, voice and export.</div>'
            )
        return original_html(value, *args, **kwargs)

    gr.Tab = tab_wrapper
    gr.HTML = html_wrapper
    detailed._translate_with_state = _translate_with_state_auto_safe
    detailed._render_m5_ui = _render_with_mix_summary
    try:
        return previous.build_app()
    finally:
        gr.Tab = original_tab
        gr.HTML = original_html
        detailed._translate_with_state = original_translate
        detailed._render_m5_ui = original_render
