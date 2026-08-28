from __future__ import annotations

from typing import Any

import gradio as gr

from .authenticated_web import (
    SOURCE_TYPE,
    acquire_single_authenticated_source,
    browser_runtime_status,
    clear_all_sessions,
    inspect_authenticated_url,
    inspection_summary,
    open_login_browser,
    pending_item_ids,
    prepare_browser_runtime,
    run_authenticated_magic_queue,
)
from .batch_flow import download_groups, queue_rows
from .progress import ProgressEstimator
from .source_providers import SourceInspection


_INSTALLED = False
_COURSE_CSS = r"""
.dl-course-source {
  margin: 4px 0 8px 0 !important;
  padding: 12px !important;
  border: 1px solid rgba(43, 108, 66, 0.55) !important;
  border-radius: 10px !important;
  background: rgba(7, 18, 11, 0.52) !important;
}
.dl-course-source > .form,
.dl-course-source > .wrap {
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.dl-course-actions {
  gap: 10px !important;
}
"""


def _duration_label(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f" · {hours}:{minutes:02d}:{secs:02d}"
    return f" · {minutes}:{secs:02d}"


def _lesson_choices(inspection: SourceInspection) -> list[tuple[str, str]]:
    return [
        (
            f"{item.index:02d} · {item.title}{_duration_label(item.duration_seconds)}",
            item.id,
        )
        for item in inspection.items
    ]


def _inspect_course_ui(url: str):
    try:
        inspection = inspect_authenticated_url(url)
        choices = _lesson_choices(inspection)
        selected = list(pending_item_ids(inspection)) if not inspection.login_required and not inspection.drm_protected else []
        status = inspection_summary(inspection)
        if inspection.login_required:
            status = f"⚠ **Login required** · {status}"
        elif inspection.drm_protected:
            status = f"⚠ **DRM protected** · {status}"
        else:
            status = f"✓ **Course source ready** · {status}"
        return (
            status,
            gr.CheckboxGroup(
                choices=choices,
                value=selected,
                interactive=not inspection.login_required and not inspection.drm_protected,
            ),
            inspection.to_dict(),
        )
    except Exception as exc:
        return (
            f"⚠ **Could not inspect course / website** · {exc}",
            gr.CheckboxGroup(choices=[], value=[], interactive=False),
            {},
        )


def _open_login_ui(url: str) -> str:
    try:
        return f"✓ {open_login_browser(url)}"
    except Exception as exc:
        return f"⚠ **Could not open sign-in browser** · {exc}"


def _select_all_lessons(state: dict[str, Any] | None):
    try:
        inspection = SourceInspection.from_dict(state or {})
    except Exception:
        return gr.CheckboxGroup(value=[])
    return gr.CheckboxGroup(value=list(pending_item_ids(inspection)))


def _clear_lesson_selection():
    return gr.CheckboxGroup(value=[])


def _selection_note(values: list[str] | None, state: dict[str, Any] | None) -> str:
    count = len(values or [])
    total = 0
    try:
        total = len(SourceInspection.from_dict(state or {}).items)
    except Exception:
        pass
    if not total:
        return "Inspect a course or lesson first."
    return f"**{count} of {total} lesson(s) selected** · queue work is sequential and completed lessons resume without reprocessing."


def _toggle_magic_source(source_type: str):
    youtube = source_type == "YouTube"
    local = source_type == "Local file"
    course = source_type == SOURCE_TYPE
    if youtube:
        note = "Paste one video, playlist, or channel URL. Collections are expanded into one sequential queue."
    elif local:
        note = "Choose one or more files. They are processed one at a time, never in parallel."
    else:
        note = "Open/sign in if needed, inspect the course or lesson, choose lessons, then run the same Magic Flow pipeline. DRM is never bypassed."
    return (
        gr.Textbox(visible=youtube),
        gr.File(visible=local, file_count="multiple"),
        gr.Column(visible=course),
        note,
    )


def _prepare_browser_ui(progress: gr.Progress = gr.Progress(track_tqdm=True)) -> str:
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    try:
        return f"✓ {prepare_browser_runtime(progress_callback=update)}"
    except Exception as exc:
        return f"⚠ **Browser setup needs attention** · {exc}"


def _clear_sessions_ui() -> str:
    try:
        count = clear_all_sessions()
        noun = "session" if count == 1 else "sessions"
        return f"✓ Cleared {count} local website {noun}."
    except Exception as exc:
        return f"⚠ **Could not clear website sessions** · {exc}"


def _course_queue_status(result, inspection: SourceInspection) -> str:
    done = len(result.succeeded)
    failed = len(result.failed)
    cancelled = len(result.cancelled)
    total = len(result.items)
    location = f"Movies/DubLocal/{inspection.provider_label}/{inspection.title}"
    if cancelled:
        return (
            f"■ **Course queue stopped** · {done}/{total} completed · {failed} failed · "
            f"{cancelled} cancelled/not started · completed outputs were kept in {location}."
        )
    if failed:
        return (
            f"⚠ **Course queue complete** · {done}/{total} succeeded · {failed} failed · "
            f"successful outputs were kept in {location}. Retry later resumes completed lessons."
        )
    return f"✓ **Course queue complete · OK** · {done}/{total} succeeded · outputs saved in {location}."


def install_course_import_ui(product_ui) -> None:
    """Install authenticated Course / Website as a source, never as a second pipeline."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_run_ui = product_ui._run_batch_magic_ui
    original_settings = product_ui._build_settings_injections
    original_build = product_ui.build_app

    def run_ui_with_course(
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
        course_url: str = "",
        course_selected: list[str] | None = None,
        course_state: dict[str, Any] | None = None,
        progress: gr.Progress = gr.Progress(track_tqdm=True),
    ):
        # Preserve the existing YouTube/local queue exactly. Course import is only an
        # acquisition layer in front of the same Magic Flow engine.
        if source_type != SOURCE_TYPE:
            return original_run_ui(
                source_type,
                youtube_url,
                local_files,
                rights_confirmed,
                target_language,
                tasks,
                subtitle_policy,
                local_transcription_policy,
                keep_original_audio_track,
                container,
                video_quality,
                progress,
            )

        estimator = ProgressEstimator()

        def update(fraction: float, label: str) -> None:
            progress(fraction, desc=estimator.message(fraction, label))

        effective_subtitle_policy = (
            local_transcription_policy
            if subtitle_policy == "local" and local_transcription_policy in {"local-fast", "local-best"}
            else subtitle_policy
        )
        try:
            inspection = SourceInspection.from_dict(course_state or {})
            if not inspection.items:
                inspection = inspect_authenticated_url(course_url)
            result = run_authenticated_magic_queue(
                inspection=inspection,
                selected_ids=course_selected,
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
            return [], [], [], [], [], f"⚠ **Course queue failed to start** · {exc}"

        source_outputs, translated_outputs, voice_outputs, media_outputs = download_groups(result)
        return (
            source_outputs,
            translated_outputs,
            voice_outputs,
            media_outputs,
            queue_rows(result),
            _course_queue_status(result, inspection),
        )

    product_ui._run_batch_magic_ui = run_ui_with_course

    def build_magic_panel_with_course(original_html) -> None:
        with gr.Group(elem_classes=["dl-magic-shell"]):
            original_html('<div class="dl-magic-title">Magic Flow</div>')
            original_html(
                '<div class="dl-magic-subtitle">One video, many files, or an authenticated course: choose the source and desired result. DubLocal resolves everything into one sequential local pipeline.</div>'
            )

            source_type = gr.Radio(
                choices=["YouTube", "Local file", SOURCE_TYPE],
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

            with gr.Column(visible=False, elem_classes=["dl-course-source"]) as course_panel:
                course_url = gr.Textbox(
                    label="Course or lesson URL",
                    placeholder="https://www.domestika.org/... or another authenticated course/video page",
                )
                with gr.Row(elem_classes=["dl-course-actions"]):
                    login_button = gr.Button("Open / Sign in", variant="secondary")
                    inspect_button = gr.Button("Inspect course / lesson", variant="primary")
                course_status = gr.Markdown(
                    f"**Authenticated website browser** · {browser_runtime_status()}",
                    elem_classes=["dl-stage-status"],
                )
                lessons = gr.CheckboxGroup(
                    label="Lessons",
                    choices=[],
                    value=[],
                    interactive=False,
                )
                course_state = gr.State({})
                with gr.Row():
                    select_all = gr.Button("Select pending", variant="secondary")
                    clear_selection = gr.Button("Clear selection", variant="secondary")
                selection_note = gr.Markdown(
                    "Inspect a course or lesson first.",
                    elem_classes=["dl-queue-note"],
                )

                login_button.click(fn=_open_login_ui, inputs=[course_url], outputs=[course_status], queue=False)
                inspect_event = inspect_button.click(
                    fn=_inspect_course_ui,
                    inputs=[course_url],
                    outputs=[course_status, lessons, course_state],
                )
                inspect_event.then(
                    fn=_selection_note,
                    inputs=[lessons, course_state],
                    outputs=[selection_note],
                    queue=False,
                )
                select_all.click(
                    fn=_select_all_lessons,
                    inputs=[course_state],
                    outputs=[lessons],
                    queue=False,
                ).then(
                    fn=_selection_note,
                    inputs=[lessons, course_state],
                    outputs=[selection_note],
                    queue=False,
                )
                clear_selection.click(fn=_clear_lesson_selection, outputs=[lessons], queue=False).then(
                    fn=_selection_note,
                    inputs=[lessons, course_state],
                    outputs=[selection_note],
                    queue=False,
                )
                lessons.change(
                    fn=_selection_note,
                    inputs=[lessons, course_state],
                    outputs=[selection_note],
                    queue=False,
                )

            queue_note = gr.Markdown(
                "Paste one video, playlist, or channel URL. Collections are expanded into one sequential queue.",
                elem_classes=["dl-queue-note"],
            )
            source_type.change(
                fn=_toggle_magic_source,
                inputs=[source_type],
                outputs=[youtube_url, local_files, course_panel, queue_note],
                queue=False,
            )

            rights = gr.Checkbox(
                label="I confirm that I have legitimate access to this content and the right or legal authority to process it for my intended use",
                value=False,
            )

            with gr.Row():
                target_language = gr.Dropdown(
                    label="Output language",
                    choices=product_ui.base.TARGET_LANGUAGE_CHOICES,
                    value="en",
                    interactive=True,
                )
                tasks = gr.CheckboxGroup(
                    label="Create",
                    choices=product_ui.MAGIC_TASK_CHOICES,
                    value=["subtitles", "translate", "voice", "media"],
                )

            with gr.Accordion("More options", open=False):
                original_html(
                    '<div class="dl-compact-note">The same settings apply to every queued item. A failed item does not discard successful items or stop the rest of the queue.</div>'
                )
                subtitle_policy = gr.Dropdown(
                    label="Subtitle source",
                    choices=product_ui.MAGIC_SUBTITLE_POLICY_CHOICES,
                    value="auto",
                )
                local_transcription_policy = gr.Dropdown(
                    label="Local transcription quality",
                    choices=product_ui.MAGIC_LOCAL_TRANSCRIPTION_CHOICES,
                    value=product_ui._default_local_transcription_policy(),
                    visible=False,
                    info="FAST uses Base for speed. BEST uses Accurate Large v3 Turbo Q5 for maximum transcription quality.",
                )
                subtitle_policy.change(
                    fn=product_ui._toggle_local_transcription_quality,
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
                        choices=product_ui.CONTAINER_CHOICES,
                        value="mkv",
                    )
                    quality = gr.Dropdown(
                        label="Video quality",
                        choices=product_ui.VIDEO_QUALITY_CHOICES,
                        value="source",
                    )
                original_html(
                    '<div class="dl-compact-note"><strong>Local files:</strong> outputs are copied beside each source. <strong>YouTube:</strong> copies go to Downloads/DubLocal. <strong>Courses:</strong> copies are organized under Movies/DubLocal/Provider/Course. Authenticated source media stays temporary by default.</div>'
                )

            run = gr.Button("Run Magic Flow", variant="primary")
            local_files.change(
                fn=product_ui._local_queue_status,
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
                    source_output = gr.File(label="Source subtitles", file_count="multiple", interactive=False)
                    translated_output = gr.File(label="Translated subtitles", file_count="multiple", interactive=False)
                with gr.Row():
                    voice_output = gr.File(label="Voice-only WAV", file_count="multiple", interactive=False)
                    media_output = gr.File(label="Output media", file_count="multiple", interactive=False)
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
                fn=product_ui._run_batch_magic_ui,
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
                    course_url,
                    lessons,
                    course_state,
                ],
                outputs=[source_output, translated_output, voice_output, media_output, queue_table, status],
            )

    product_ui._build_batch_magic_panel = build_magic_panel_with_course

    def settings_with_authenticated_web(original_html) -> None:
        with gr.Accordion("Authenticated Websites", open=False):
            status = gr.Markdown(browser_runtime_status(), elem_classes=["console"])
            original_html(
                '<div class="dl-note">DubLocal uses its own local Chromium profile. You enter credentials directly on the website; DubLocal never asks for or stores your password. Sessions/cookies stay local and can be cleared here. Protected DRM streams are detected/refused rather than bypassed.</div>'
            )
            with gr.Row():
                prepare = gr.Button("Prepare authenticated website browser", variant="primary")
                clear = gr.Button("Clear all website sessions", variant="secondary")
            prepare.click(fn=_prepare_browser_ui, outputs=[status])
            clear.click(fn=_clear_sessions_ui, outputs=[status], queue=False)
        original_settings(original_html)

    product_ui._build_settings_injections = settings_with_authenticated_web

    def build_app_with_course():
        original_radio = gr.Radio
        original_textbox = gr.Textbox
        original_toggle_source = product_ui.base._toggle_source
        original_scan = product_ui.detailed._scan_source_ui
        original_source_card = product_ui.detailed._source_card_status_human

        def radio_factory(*args: Any, **kwargs: Any):
            choices = kwargs.get("choices")
            if choices is None and args:
                choices = args[0]
            if list(choices or []) == ["YouTube", "Local file"]:
                if args:
                    args = (["YouTube", "Local file", SOURCE_TYPE], *args[1:])
                else:
                    kwargs = dict(kwargs)
                    kwargs["choices"] = ["YouTube", "Local file", SOURCE_TYPE]
            return original_radio(*args, **kwargs)

        def textbox_factory(*args: Any, **kwargs: Any):
            if kwargs.get("label") == "YouTube URL":
                kwargs = dict(kwargs)
                kwargs["label"] = "YouTube / Course website URL"
                kwargs["placeholder"] = "https://www.youtube.com/... or an authenticated direct lesson URL"
            return original_textbox(*args, **kwargs)

        def toggle_source(source_type: str):
            if source_type == SOURCE_TYPE:
                return gr.Textbox(visible=True), gr.File(visible=False)
            return original_toggle_source(source_type)

        def scan_source(
            source_type: str,
            youtube_url: str,
            local_file: str | None,
            progress: gr.Progress = gr.Progress(track_tqdm=True),
        ):
            if source_type != SOURCE_TYPE:
                return original_scan(source_type, youtube_url, local_file, progress)
            estimator = ProgressEstimator()

            def update(fraction: float, label: str) -> None:
                progress(fraction * 0.35, desc=estimator.message(fraction * 0.35, label))

            acquired = acquire_single_authenticated_source(youtube_url, progress_callback=update)
            result = list(original_scan("Local file", "", str(acquired.path), progress))
            if len(result) >= 3 and isinstance(result[2], dict):
                info = dict(result[2])
                info.update(
                    {
                        "kind": "authenticated_web",
                        "title": acquired.lesson_title or acquired.title,
                        "course_title": acquired.course_title,
                        "provider_id": acquired.provider_id,
                        "provider_label": str(acquired.metadata.get("provider_label") or acquired.provider_id),
                        "source_url": acquired.source_url,
                    }
                )
                result[2] = info
            return tuple(result)

        def source_card(info: dict | None) -> str:
            value = info or {}
            if value.get("kind") != "authenticated_web":
                return original_source_card(info)
            title = str(value.get("title") or "Lesson").replace("\n", " ").strip()
            provider = str(value.get("provider_label") or "Authenticated website")
            duration = product_ui.base._duration_compact(value)
            tracks = len(value.get("subtitle_tracks", []) or [])
            return f"✓ **Loaded · OK** · Course / Website · {provider} · {title} · {duration} · {tracks} source subtitle track(s)"

        gr.Radio = radio_factory
        gr.Textbox = textbox_factory
        product_ui.base._toggle_source = toggle_source
        product_ui.detailed._scan_source_ui = scan_source
        product_ui.detailed._source_card_status_human = source_card
        try:
            return original_build()
        finally:
            gr.Radio = original_radio
            gr.Textbox = original_textbox
            product_ui.base._toggle_source = original_toggle_source
            product_ui.detailed._scan_source_ui = original_scan
            product_ui.detailed._source_card_status_human = original_source_card

    product_ui.MATRIX_CSS += _COURSE_CSS
    product_ui.build_app = build_app_with_course
