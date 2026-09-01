from __future__ import annotations

from pathlib import Path
from typing import Any

import gradio as gr

from . import __version__
from . import ui as base_ui
from .adaptive_audio import (
    MIX_STRATEGY_CHOICES,
    advanced_mix_preference,
    audio_mix_status,
    last_mix_summary,
    prepare_separation_ui,
    set_advanced_mix_preference,
)
from .adaptive_contextual import (
    active_recommendation,
    adaptive_contextual_translation_status,
    prepare_recommended_contextual_translation,
    remove_all_contextual_model_registrations,
)
from .authenticated_web import (
    SOURCE_TYPE as COURSE_SOURCE_TYPE,
    browser_runtime_status,
    clear_all_sessions,
    inspect_authenticated_url,
    inspection_summary,
    open_login_browser,
    pending_item_ids,
    prepare_browser_runtime,
)
from .batch_flow import download_groups, queue_rows
from .beta_branding import _BRAND_CSS, branded_header
from .caption_ux import caption_inventory_text, curate_caption_info
from .contextual_progress import translate_srt_contextual_with_progress
from .dependencies import local_resource_status
from .job_control import (
    begin_job,
    cancel_requested,
    end_job,
    job_active,
    release_session_resources,
    request_cancel,
)
from .magic_flow import MAGIC_LOCAL_TRANSCRIPTION_CHOICES, MAGIC_SUBTITLE_POLICY_CHOICES
from .media import DubLocalError
from .model_setup import (
    mark_first_run_skipped,
    model_setup_state,
    model_setup_summary,
    prepare_recommended_models,
)
from .normal_update import update_dublocal_ui, updater_idle_status
from .output_naming import friendly_subtitle_path
from .output_profiles import PROFILE_CHOICES, load_profiles, profile_summary, reset_profiles, save_profiles
from .production_course import run_course_queue
from .production_pipeline import _profiled_render, _profiled_subtitle_package
from .production_queue import run_processing_queue
from .progress import ProgressEstimator
from .progress_operations import generate_voice_track_with_progress, install_whisper_model_with_progress
from .source_providers import SourceInspection
from .stage_status import subtitles_ready_status, translation_ready_status, voice_ready_status
from .storage_cleanup import clean_temporary_files_status, prune_stale_jobs_only, storage_status_markdown
from .subtitle_export import SUBTITLE_FORMAT_CHOICES, export_subtitle
from .transcription import model_manager_status, remove_whisper_model, whisper_model_path
from .translation import translated_segments_to_rows, translation_manager_status
from .tts import voice_segments_to_rows
from .tts_provider_refinement import (
    prepare_registered_provider_ui,
    register_custom_provider_ui,
    registered_provider_choices,
)
from .tts_provider_registry import provider_status_text
from .voice_engine import (
    default_voice,
    prepare_voice_engine,
    suggested_voice_language,
    voice_choices,
    voice_engine_status,
    voice_language_choices,
)
from .voice_selection import AUTO_VOICE_VALUE, auto_default_voice, auto_voice_choices, resolve_auto_voice_plan
from .voice_text import prepare_voice_srt


STANDARD_TASK_CHOICES = [
    ("Subtitles", "subtitles"),
    ("Translate", "translate"),
    ("Voice-over", "voice"),
    ("Media file · original + subtitles if Translate/Voice are off", "media"),
]
AUDIO_DELIVERY_CHOICES = [
    ("Keep original audio as a separate selectable track", "keep-original"),
    ("Single voice for the whole item · best overall match", "single-voice"),
    ("Burn subtitles into Shareable MP4 · always visible in messaging apps", "burn-share-subs"),
]
CONTAINER_CHOICES = [
    ("MKV · safest multi-track output", "mkv"),
    ("MP4 · compatible", "mp4"),
    ("MP4 · Shareable · WhatsApp / Telegram · H.264 + AAC", "share"),
]
ADVANCED_CONTAINER_CHOICES = [
    ("MKV · safest multi-track output", "mkv"),
    ("MP4 · compatible", "mp4"),
]
VIDEO_QUALITY_CHOICES = [
    ("Original / best available", "source"),
    ("2160p max", "2160"),
    ("1440p max", "1440"),
    ("1080p max", "1080"),
    ("720p max", "720"),
    ("480p max", "480"),
]
TRANSLATION_MODE_CHOICES = [
    (f"Recommended for this Mac · {active_recommendation().label}", "contextual"),
    ("Fast legacy · OPUS · sentence-level", "opus"),
]

_EXAMPLE_MANIFEST = """{
  "schema_version": 1,
  "id": "my-russian-kokoro",
  "label": "My vetted Russian Kokoro mirror",
  "language": "ru",
  "language_label": "Russian",
  "backend": "kokoro-local",
  "frontend": "russian-v2",
  "source": {"type": "local", "path": "/Users/me/Models/my-russian-kokoro"},
  "license": {
    "id": "OpenRAIL",
    "commercial_use": true,
    "redistribution": "not-bundled",
    "source": "model-card-or-license-location",
    "attribution": "required attribution text"
  },
  "config_file": "kokoro-config.json",
  "voices": [{
    "id": "rf_sveta",
    "label": "Sveta · female",
    "gender": "female",
    "model_file": "kokoro-ru-v2-base.pth",
    "voice_file": "voices/sveta.pt"
  }],
  "default_voice": "rf_sveta",
  "preferred": true
}"""

_PRODUCT_CSS = r"""
:root {
  --primary-400: #42ef83 !important;
  --primary-500: #42ef83 !important;
  --primary-600: #2bd26d !important;
  --color-accent: #42ef83 !important;
  --loader-color: var(--dl-green) !important;
}
.gradio-container [data-testid="status-tracker"] .progress-bar,
.gradio-container .progress-bar { background-color: var(--dl-green) !important; }
button[role="tab"][aria-selected="true"], .tab-nav button.selected, .tabs button.selected {
  color: var(--dl-green) !important;
  border-color: var(--dl-green) !important;
}
.dl-version-card {
  display:flex; align-items:center; justify-content:space-between; gap:12px;
  margin:8px 0 18px; padding:12px 14px; border:1px solid var(--dl-border);
  border-radius:10px; background:rgba(8,18,12,.72);
}
.dl-version-number { color:var(--dl-green); font:700 14px ui-monospace,SFMono-Regular,Menlo,monospace; }
.dl-main-mode-note,.dl-compact-note,.dl-queue-note,.dl-stop-note {
  color:var(--dl-muted)!important; font-size:12px!important; line-height:1.45!important;
}
.dl-queue-note { margin:6px 0 10px!important; }
.dl-magic-shell {
  border:1px solid rgba(66,239,131,.58)!important; border-radius:12px!important;
  padding:20px 22px!important; margin:8px 0 18px!important;
  background:linear-gradient(180deg,rgba(9,28,17,.72),rgba(7,16,10,.72))!important;
}
.dl-magic-shell > .form,.dl-magic-shell > .wrap {
  padding:0!important; margin:0!important; border:0!important; background:transparent!important; box-shadow:none!important;
}
.dl-magic-shell .block:has(.dl-magic-title),.dl-magic-shell .block:has(.dl-magic-subtitle) {
  border:0!important; background:transparent!important; box-shadow:none!important; padding:0!important;
}
.dl-magic-title { color:var(--dl-green)!important; font-weight:700!important; font-size:16px!important; margin-bottom:2px!important; }
.dl-magic-subtitle { color:var(--dl-muted)!important; font-size:12px!important; margin-bottom:12px!important; }
.dl-stage-status {
  margin:8px 0 6px!important; padding:10px 12px!important; border:1px solid rgba(43,108,66,.62)!important;
  border-radius:8px!important; background:rgba(7,18,11,.58)!important;
}
.dl-magic-actions { display:flex!important; align-items:stretch!important; gap:12px!important; margin:12px 0 6px!important; width:100%!important; }
.dl-magic-actions button { min-height:44px!important; width:100%!important; margin:0!important; border-radius:8px!important; font-weight:650!important; }
.dl-magic-actions button.primary { flex:2 1 0!important; }
.dl-stop-button { flex:1 1 0!important; background:#101b15!important; border:1px solid rgba(66,239,131,.52)!important; color:var(--dl-green-soft)!important; }
.dl-model-setup-card {
  border:1px solid rgba(66,239,131,.50)!important; border-radius:12px!important; padding:18px!important;
  margin:4px 0 18px!important; background:rgba(7,18,11,.76)!important; box-shadow:none!important;
}
.dl-model-setup-card > .form,.dl-model-setup-card > .wrap { padding:0!important; border:0!important; background:transparent!important; box-shadow:none!important; }
.dl-model-setup-title { color:var(--dl-green)!important; font-size:17px!important; font-weight:700!important; }
.dl-model-setup-copy { color:var(--dl-muted)!important; font-size:12px!important; margin:0 0 10px!important; }
.dl-update-card { border:1px solid rgba(66,239,131,.46)!important; border-radius:12px!important; padding:14px!important; background:rgba(7,18,11,.72)!important; }
.dl-course-source { margin:4px 0 8px!important; padding:12px!important; border:1px solid rgba(43,108,66,.55)!important; border-radius:10px!important; background:rgba(7,18,11,.52)!important; }
@media (max-width:720px) {
  .dl-magic-shell { padding:16px!important; }
  .dl-magic-actions { flex-direction:column!important; gap:8px!important; }
}
"""
MATRIX_CSS = base_ui.MATRIX_CSS + _PRODUCT_CSS + _BRAND_CSS


def _error(message: object) -> str:
    return f"```text\n[error] {message}\n```"


def _progress(progress: gr.Progress):
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    return update


def _header() -> str:
    return branded_header(
        """
        <div class="dl-header">
          <div class="dl-brand">DubLocal<span class="dl-cursor">_</span><span class="dl-local">LOCAL</span></div>
          <div class="dl-subtitle">Subtitles, contextual translation and local AI voice-over — processed on your Mac.</div>
        </div>
        """
    )


def _version_card() -> str:
    return (
        '<div class="dl-version-card">'
        '<div><strong>DubLocal</strong><div class="dl-note">Local application</div></div>'
        f'<div class="dl-version-number">v{__version__}</div>'
        '</div>'
    )


def _default_local_transcription_policy() -> str:
    try:
        return "local-best" if whisper_model_path("large-v3-turbo-q5_0").is_file() else "local-fast"
    except Exception:
        return "local-fast"


def _toggle_local_transcription_quality(policy: str):
    return gr.Dropdown(visible=policy == "local")


def _toggle_standard_source(source_type: str):
    youtube = source_type == "YouTube"
    local = source_type == "Local file"
    course = source_type == COURSE_SOURCE_TYPE
    if youtube:
        note = "Paste one video, playlist, or channel URL. Collections are expanded into one sequential queue."
    elif local:
        note = "Choose one or more files. They are processed one at a time, never in parallel."
    else:
        note = "Open/sign in if needed, inspect the course or lesson, choose lessons, then process the same local workflow. DRM is never bypassed."
    return gr.Textbox(visible=youtube), gr.File(visible=local, file_count="multiple"), gr.Column(visible=course), note


def _local_queue_status(files: Any):
    if not files:
        return "Choose one or more local media files.", gr.Button(value="Start Processing")
    if isinstance(files, (str, bytes)) or getattr(files, "name", None):
        count = 1
    else:
        count = len(list(files))
    noun = "file" if count == 1 else "files"
    return (
        f"**{count} {noun} selected** · sequential processing · outputs are saved next to each source file.",
        gr.Button(value=f"Process {count} queued {noun}"),
    )


def _apply_audio_preferences(tasks: list[str] | None, preferences: list[str] | None) -> tuple[list[str], bool]:
    selected = [str(item) for item in (tasks or [])]
    prefs = {str(item) for item in (preferences or [])}
    for marker in ("single-voice", "burn-share-subs"):
        if marker in prefs and marker not in selected:
            selected.append(marker)
    return selected, "keep-original" in prefs


def _stop_processing() -> None:
    if not job_active():
        try:
            gr.Info("No processing job is currently running.")
        except Exception:
            pass
        return
    count = request_cancel()
    try:
        suffix = f" Stopping {count} active helper process{'es' if count != 1 else ''}." if count else ""
        gr.Warning("Stopping the current job. Completed outputs will be kept; queued items will not start." + suffix)
    except Exception:
        pass


def _run_standard_ui(
    source_type: str,
    youtube_url: str,
    local_files: Any,
    rights_confirmed: bool,
    target_language: str,
    tasks: list[str] | None,
    subtitle_policy: str,
    local_transcription_policy: str,
    audio_preferences: list[str] | None,
    container: str,
    video_quality: str,
    course_url: str,
    course_selected: list[str] | None,
    course_state: dict[str, Any] | None,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress(progress)
    selected_tasks, keep_original = _apply_audio_preferences(tasks, audio_preferences)
    effective_policy = (
        local_transcription_policy
        if subtitle_policy == "local" and local_transcription_policy in {"local-fast", "local-best"}
        else subtitle_policy
    )

    begin_job()
    try:
        if source_type == COURSE_SOURCE_TYPE:
            inspection = SourceInspection.from_dict(course_state or {})
            if not inspection.items:
                inspection = inspect_authenticated_url(course_url)
            result = run_course_queue(
                inspection=inspection,
                selected_ids=course_selected,
                rights_confirmed=rights_confirmed,
                target_language=target_language,
                tasks=selected_tasks,
                subtitle_policy=effective_policy,
                keep_original_audio_track=keep_original,
                container=container,
                video_quality=video_quality,
                progress_callback=update,
            )
            location = f"Movies/DubLocal/{inspection.provider_label}/{inspection.title}"
        else:
            result = run_processing_queue(
                source_type=source_type,
                youtube_url=youtube_url,
                local_files=local_files,
                rights_confirmed=rights_confirmed,
                target_language=target_language,
                tasks=selected_tasks,
                subtitle_policy=effective_policy,
                keep_original_audio_track=keep_original,
                container=container,
                video_quality=video_quality,
                progress_callback=update,
            )
            location = (
                "next to each original local file"
                if source_type == "Local file"
                else "Downloads/DubLocal"
            )

        source_outputs, translated_outputs, voice_outputs, media_outputs = download_groups(result)
        rows = queue_rows(result)
        done = len(result.succeeded)
        failed = len(result.failed)
        cancelled = len(result.cancelled)
        total = len(result.items)
        if cancelled or cancel_requested():
            status = f"■ **Queue stopped** · {done}/{total} completed · {cancelled or max(0, total-done)} cancelled/not started · completed outputs were kept."
        elif failed:
            status = f"⚠ **Queue complete** · {done}/{total} succeeded · {failed} failed · successful outputs were kept in {location}."
        else:
            status = f"✓ **Queue complete · OK** · {done}/{total} succeeded · outputs saved in {location}."
        return source_outputs, translated_outputs, voice_outputs, media_outputs, rows, status
    except Exception as exc:
        return [], [], [], [], [], f"⚠ **Queue failed to start** · {exc}"
    finally:
        end_job()
        try:
            prune_stale_jobs_only()
        except Exception:
            pass


def _inspect_course_ui(url: str):
    try:
        inspection = inspect_authenticated_url(url)
        choices = [
            (f"{item.index:02d} · {item.title}" + (f" · {int(item.duration_seconds)//60}:{int(item.duration_seconds)%60:02d}" if item.duration_seconds else ""), item.id)
            for item in inspection.items
        ]
        selected = list(pending_item_ids(inspection)) if not inspection.login_required and not inspection.drm_protected else []
        prefix = "⚠ Login required" if inspection.login_required else "⚠ DRM protected" if inspection.drm_protected else "✓ Course source ready"
        return f"{prefix} · {inspection_summary(inspection)}", gr.CheckboxGroup(choices=choices, value=selected, interactive=not inspection.login_required and not inspection.drm_protected), inspection.to_dict()
    except Exception as exc:
        return f"⚠ **Could not inspect course / website** · {exc}", gr.CheckboxGroup(choices=[], value=[], interactive=False), {}


def _open_login_ui(url: str) -> str:
    try:
        return f"✓ {open_login_browser(url)}"
    except Exception as exc:
        return f"⚠ **Could not open sign-in browser** · {exc}"


def _select_pending_lessons(state: dict[str, Any] | None):
    try:
        inspection = SourceInspection.from_dict(state or {})
        return gr.CheckboxGroup(value=list(pending_item_ids(inspection)))
    except Exception:
        return gr.CheckboxGroup(value=[])


def _selection_note(values: list[str] | None, state: dict[str, Any] | None) -> str:
    try:
        total = len(SourceInspection.from_dict(state or {}).items)
    except Exception:
        total = 0
    if not total:
        return "Inspect a course or lesson first."
    return f"**{len(values or [])} of {total} lesson(s) selected** · completed lessons resume without reprocessing."


def _prepare_models_ui(progress: gr.Progress = gr.Progress(track_tqdm=True)):
    try:
        result = prepare_recommended_models(progress_callback=_progress(progress))
        return result, gr.Column(visible=False)
    except Exception as exc:
        return f"### Setup needs attention\n{exc}", gr.Column(visible=True)


def _skip_setup_ui():
    mark_first_run_skipped()
    return gr.Column(visible=False)


def _build_model_setup_card(*, first_run: bool) -> gr.Column:
    state = model_setup_state()
    panel = gr.Column(visible=state.first_run_pending if first_run else True, elem_classes=["dl-model-setup-card"])
    with panel:
        gr.HTML('<div class="dl-model-setup-title">' + ("Welcome · model setup" if first_run else "Model Setup") + '</div>')
        gr.HTML('<div class="dl-model-setup-copy">DubLocal chooses a practical local model set for this computer. Nothing is downloaded until you approve it.</div>')
        status = gr.Markdown(model_setup_summary())
        with gr.Row():
            prepare = gr.Button("Set up recommended models" if first_run else "Prepare / repair recommended setup", variant="primary")
            skip = gr.Button("Skip for now", variant="secondary") if first_run else None
        prepare.click(fn=_prepare_models_ui, outputs=[status, panel])
        if skip is not None:
            skip.click(fn=_skip_setup_ui, outputs=[panel], queue=False)
    return panel


def _advanced_scan(source_type: str, youtube_url: str, local_file: str | None, progress: gr.Progress = gr.Progress(track_tqdm=True)):
    status, selector, info, rows = base_ui._scan_source_ui(source_type, youtube_url, local_file, progress)
    if not info:
        return status, selector, info, rows, "⚠ **Source not loaded**"
    curated = curate_caption_info(info)
    tracks = curated.get("subtitle_tracks", []) or []
    choices = [(str(item.get("label") or "Subtitle track"), item.get("value")) for item in tracks]
    selector = gr.Dropdown(label="Available subtitles", choices=choices, value=choices[0][1] if choices else None, interactive=bool(choices))
    title = str(curated.get("title") or "Media").replace("\n", " ").strip()
    kind = "YouTube" if curated.get("kind") == "youtube" else "Local file"
    inventory = caption_inventory_text(curated)
    card = f"✓ **Loaded · OK** · {kind} · {title}"
    if inventory:
        card += f" · {inventory}"
    return status, selector, curated, rows, card


def _friendly_path(path: str | None, info: dict | None, language: str | None) -> str:
    if not path:
        return ""
    return str(friendly_subtitle_path(path, info or {}, language))


def _advanced_extract(info: dict, track: str | None, rights: bool, output_format: str, progress: gr.Progress = gr.Progress(track_tqdm=True)):
    download, rows, status, path, language, card = base_ui._extract_ui(info, track, rights, output_format, progress)
    if path:
        path = _friendly_path(path, info, language)
        download = str(export_subtitle(path, output_format))
    return download, rows, status, path, gr.Dropdown(choices=base_ui.LANGUAGE_CHOICES, value=language, interactive=True), card


def _advanced_transcribe(info: dict, rights: bool, model_id: str, language: str, output_format: str, progress: gr.Progress = gr.Progress(track_tqdm=True)):
    download, rows, status, path, detected, card = base_ui._transcribe_ui(info, rights, model_id, language, output_format, progress)
    if path:
        path = _friendly_path(path, info, detected)
        download = str(export_subtitle(path, output_format))
    return download, rows, status, path, gr.Dropdown(choices=base_ui.LANGUAGE_CHOICES, value=detected, interactive=True), card


def _advanced_translate(mode: str, subtitle_path: str, source_language: str, target_language: str, source_info: dict | None, progress: gr.Progress = gr.Progress(track_tqdm=True)):
    if not subtitle_path:
        return None, [], _error("Extract or transcribe subtitles first."), "", translation_ready_status(None, [], source_language, target_language)
    selected_source = source_language
    update = _progress(progress)
    try:
        if mode == "contextual":
            result = translate_srt_contextual_with_progress(subtitle_path, selected_source, target_language, progress_callback=update)
            output = _friendly_path(str(result.srt_path), source_info, target_language)
            rows = translated_segments_to_rows(result.segments)
            status = f"```text\n[done] contextual subtitle translation complete\n[route] {result.route}\n[segments] {len(result.segments)} · original timings preserved\n[output] {Path(output).name}\n```"
        else:
            if selected_source == "auto":
                raise DubLocalError("Fast legacy OPUS translation needs a known source language. Choose From manually or use Contextual quality with Auto.")
            output, rows, status = base_ui.translate_selected(subtitle_path, selected_source, target_language)
            if output:
                output = _friendly_path(output, source_info, target_language)
        preview = [[row[0], row[1], row[3], row[2]] if len(row) >= 4 else list(row) for row in rows]
        card = translation_ready_status(output, preview, selected_source, target_language)
        return output, preview, status, output or "", card
    except Exception as exc:
        return None, [], _error(exc), "", translation_ready_status(None, [], source_language, target_language)


def _voice_controls(timeline_source: str, source_language: str, target_language: str):
    language = source_language if timeline_source == "Source subtitles" else target_language
    selected = suggested_voice_language(language)
    if not selected:
        return gr.Dropdown(value=None), gr.Dropdown(choices=[], value=None, interactive=False)
    choices = auto_voice_choices(selected)
    return gr.Dropdown(value=selected), gr.Dropdown(choices=choices, value=auto_default_voice(selected), interactive=bool(choices))


def _voice_dropdown(language: str | None):
    choices = auto_voice_choices(language)
    return gr.Dropdown(choices=choices, value=auto_default_voice(language), interactive=bool(choices))


def _advanced_voice(
    timeline_source: str,
    source_subtitle_path: str,
    translated_subtitle_path: str,
    source_info: dict | None,
    language: str | None,
    voice: str | None,
    speed: float,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    selected = source_subtitle_path if timeline_source == "Source subtitles" else translated_subtitle_path
    if not selected:
        return None, None, [], _error("Prepare the selected subtitle timeline first."), voice_ready_status(None, [], language, voice)
    if not language or not voice:
        return None, None, [], _error("No compatible local voice is selected."), voice_ready_status(None, [], language, voice)

    update = _progress(progress)
    cleaned = prepare_voice_srt(selected)
    selected_voice = voice
    plan: dict[int, str] = {}
    summary = ""
    try:
        if voice == AUTO_VOICE_VALUE:
            def analysis(fraction: float, label: str) -> None:
                update(0.16 * fraction, label)
            selected_voice, plan, summary = resolve_auto_voice_plan(cleaned, source_info or {}, language, progress_callback=analysis)
            def speech(fraction: float, label: str) -> None:
                update(0.16 + 0.84 * fraction, label)
            callback = speech
        else:
            callback = update
        result = generate_voice_track_with_progress(
            cleaned,
            language=language,
            voice=selected_voice,
            speed=float(speed),
            segment_voices=plan,
            progress_callback=callback,
        )
        rows = voice_segments_to_rows(result.segments)
        note = f"\n[auto voice] {summary}" if summary else ""
        status = (
            "```text\n[done] local voice generation complete\n"
            f"[runtime] {result.runtime_label} · {result.device}\n"
            f"[voice] {result.language} · {result.voice} · speed {result.speed:.2f}{note}\n"
            f"[segments] {len(result.segments)}\n[output] {result.wav_path.name}\n```"
        )
        path = str(result.wav_path)
        return path, path, rows, status, voice_ready_status(path, rows, language, voice)
    except Exception as exc:
        return None, None, [], _error(exc), voice_ready_status(None, [], language, voice)


def _advanced_render(
    source_info: dict,
    voice_wav: str | None,
    rights: bool,
    language: str | None,
    source_subtitle: str | None,
    translated_subtitle: str | None,
    source_language: str | None,
    translated_language: str | None,
    mode: str,
    container: str,
    video_quality: str,
    mix_strategy: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    if not rights:
        return None, "⚠ **Export failed** · confirm processing rights first."
    if not voice_wav or not language:
        return None, "⚠ **Export failed** · generate a voice track first."
    try:
        result = _profiled_render(
            source_info,
            voice_wav,
            language,
            mode=mode,
            container=container,
            output_format=container,
            video_quality=video_quality,
            source_subtitle_path=source_subtitle,
            translated_subtitle_path=translated_subtitle,
            source_language=source_language,
            translated_language=translated_language,
            mix_strategy=mix_strategy,
            progress_callback=_progress(progress),
        )
        video_note = "video stream copied · no re-encoding" if result.video_stream_copy else "video encoded to selected output profile"
        return str(result.output_path), f"✓ **Dubbed media ready · OK** · {result.output_path.name} · {video_note} · {last_mix_summary()}"
    except Exception as exc:
        return None, f"⚠ **Export failed** · {exc}"


def _advanced_package(
    source_info: dict,
    rights: bool,
    source_subtitle: str | None,
    source_language: str | None,
    container: str,
    video_quality: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    if not rights or not source_subtitle:
        return None, "⚠ **Subtitle package failed** · confirm rights and prepare source subtitles first."
    try:
        output = _profiled_subtitle_package(
            source_info,
            Path(source_subtitle),
            None,
            source_language or "auto",
            source_language or "auto",
            container=container,
            output_format=container,
            video_quality=video_quality,
            progress_callback=_progress(progress),
        )
        return str(output), f"✓ **Original + subtitles ready · OK** · {output.name} · original audio preserved."
    except Exception as exc:
        return None, f"⚠ **Subtitle package failed** · {exc}"


def _voice_engine_controls(language: str):
    choices = voice_choices(language)
    return gr.Dropdown(choices=choices, value=default_voice(language), interactive=bool(choices))


def _prepare_voice_settings(language: str, voice: str, progress: gr.Progress = gr.Progress(track_tqdm=True)):
    update = _progress(progress)
    try:
        update(0.05, "Preparing local voice engine")
        runtime = prepare_voice_engine(language, voice, 1.0)
        update(1.0, "Voice engine ready")
        return voice_engine_status(), local_resource_status(), f"```text\n[done] voice engine ready\n[runtime] {runtime}\n```"
    except Exception as exc:
        return voice_engine_status(), local_resource_status(), _error(exc)


def _prepare_contextual_settings(progress: gr.Progress = gr.Progress(track_tqdm=True)):
    update = _progress(progress)
    recommendation = active_recommendation()
    try:
        update(0.02, f"Preparing {recommendation.model_label}")
        runtime = prepare_recommended_contextual_translation()
        update(1.0, "Contextual translation ready")
        return adaptive_contextual_translation_status("en", "ru", 0), local_resource_status(), f"```text\n[done] contextual translation ready\n[profile] {recommendation.label}\n[runtime/model] {runtime}\n```"
    except Exception as exc:
        return adaptive_contextual_translation_status("en", "ru", 0), local_resource_status(), _error(exc)


def _remove_contextual_settings():
    try:
        removed = remove_all_contextual_model_registrations()
        action = f"```text\n[models] contextual registrations {'removed' if removed else 'were not installed'}\n[shared cache] kept\n```"
    except Exception as exc:
        action = _error(exc)
    return adaptive_contextual_translation_status("en", "ru", 0), local_resource_status(), action


def _install_whisper_settings(model_id: str, progress: gr.Progress = gr.Progress(track_tqdm=True)):
    try:
        path = install_whisper_model_with_progress(model_id, progress_callback=_progress(progress))
        action = f"```text\n[done] Whisper {model_id} installed and verified\n[model] {path.name}\n```"
    except Exception as exc:
        action = _error(exc)
    return model_manager_status(), local_resource_status(), action


def _remove_whisper_settings(model_id: str):
    try:
        removed = remove_whisper_model(model_id)
        action = f"```text\n[model] Whisper {model_id} {'removed' if removed else 'was not installed'}\n```"
    except Exception as exc:
        action = _error(exc)
    return model_manager_status(), local_resource_status(), action


def _save_profiles(mkv: str, mp4: str, share: str):
    values = save_profiles(mkv, mp4, share)
    return profile_summary(values)


def _reset_profiles():
    values = reset_profiles()
    return gr.Dropdown(value=values["mkv"]), gr.Dropdown(value=values["mp4"]), gr.Dropdown(value=values["share"]), profile_summary(values)


def _prepare_browser_ui(progress: gr.Progress = gr.Progress(track_tqdm=True)):
    try:
        return f"✓ {prepare_browser_runtime(progress_callback=_progress(progress))}"
    except Exception as exc:
        return f"⚠ **Browser setup needs attention** · {exc}"


def _clear_sessions_ui():
    try:
        count = clear_all_sessions()
        return f"✓ Cleared {count} local website session{'s' if count != 1 else ''}."
    except Exception as exc:
        return f"⚠ **Could not clear website sessions** · {exc}"


def _register_provider(manifest_text: str):
    status, action = register_custom_provider_ui(manifest_text)
    choices = registered_provider_choices()
    return status, action, gr.Dropdown(choices=choices, value=choices[-1][1] if choices else None, interactive=bool(choices))


def _build_standard() -> None:
    gr.HTML('<div class="dl-main-mode-note">Standard is the default for normal use. Switch to Advanced only when you need manual control of individual stages.</div>')
    if model_setup_state().first_run_pending:
        _build_model_setup_card(first_run=True)

    with gr.Group(elem_classes=["dl-magic-shell"]):
        gr.HTML('<div class="dl-magic-title">Standard workflow</div>')
        gr.HTML('<div class="dl-magic-subtitle">One video, many files, or an authenticated course: choose the source and outputs. DubLocal resolves the work into one sequential local processing queue.</div>')
        source_type = gr.Radio(choices=["YouTube", "Local file", COURSE_SOURCE_TYPE], value="YouTube", label="Source")
        youtube_url = gr.Textbox(label="YouTube video, playlist, or channel", placeholder="https://www.youtube.com/watch?v=… · /playlist?list=… · /@channel")
        local_files = gr.File(label="Local media", file_types=["video", "audio"], file_count="multiple", type="filepath", visible=False)

        with gr.Column(visible=False, elem_classes=["dl-course-source"]) as course_panel:
            course_url = gr.Textbox(label="Course or lesson URL", placeholder="https://www.domestika.org/... or another authenticated course/video page")
            with gr.Row():
                login = gr.Button("Open / Sign in", variant="secondary")
                inspect = gr.Button("Inspect course / lesson", variant="primary")
            course_status = gr.Markdown(f"**Authenticated website browser** · {browser_runtime_status()}", elem_classes=["dl-stage-status"])
            lessons = gr.CheckboxGroup(label="Lessons", choices=[], value=[], interactive=False)
            course_state = gr.State({})
            with gr.Row():
                select_pending = gr.Button("Select pending", variant="secondary")
                clear = gr.Button("Clear selection", variant="secondary")
            lesson_note = gr.Markdown("Inspect a course or lesson first.", elem_classes=["dl-queue-note"])
            login.click(fn=_open_login_ui, inputs=[course_url], outputs=[course_status], queue=False)
            inspected = inspect.click(fn=_inspect_course_ui, inputs=[course_url], outputs=[course_status, lessons, course_state])
            inspected.then(fn=_selection_note, inputs=[lessons, course_state], outputs=[lesson_note], queue=False)
            select_pending.click(fn=_select_pending_lessons, inputs=[course_state], outputs=[lessons], queue=False).then(fn=_selection_note, inputs=[lessons, course_state], outputs=[lesson_note], queue=False)
            clear.click(fn=lambda: gr.CheckboxGroup(value=[]), outputs=[lessons], queue=False).then(fn=_selection_note, inputs=[lessons, course_state], outputs=[lesson_note], queue=False)
            lessons.change(fn=_selection_note, inputs=[lessons, course_state], outputs=[lesson_note], queue=False)

        queue_note = gr.Markdown("Paste one video, playlist, or channel URL. Collections are expanded into one sequential queue.", elem_classes=["dl-queue-note"])
        source_type.change(fn=_toggle_standard_source, inputs=[source_type], outputs=[youtube_url, local_files, course_panel, queue_note], queue=False)

        rights = gr.Checkbox(label="I confirm that I have legitimate access to this content and the right or legal authority to process it for my intended use", value=False)
        with gr.Row():
            target = gr.Dropdown(label="Output language", choices=base_ui.TARGET_LANGUAGE_CHOICES, value="en", interactive=True)
            tasks = gr.CheckboxGroup(label="Outputs", choices=STANDARD_TASK_CHOICES, value=["subtitles", "translate", "voice", "media"])

        with gr.Accordion("Options", open=False):
            subtitle_policy = gr.Dropdown(label="Subtitle source", choices=MAGIC_SUBTITLE_POLICY_CHOICES, value="auto")
            transcription_quality = gr.Dropdown(label="Transcription quality", choices=MAGIC_LOCAL_TRANSCRIPTION_CHOICES, value=_default_local_transcription_policy(), visible=False, info="FAST uses Base. BEST uses Accurate Large v3 Turbo Q5.")
            subtitle_policy.change(fn=_toggle_local_transcription_quality, inputs=[subtitle_policy], outputs=[transcription_quality], queue=False)
            audio_preferences = gr.CheckboxGroup(label="Audio & delivery", choices=AUDIO_DELIVERY_CHOICES, value=["keep-original"], info="Single voice uses one best-overall local voice. Burn subtitles applies only to Shareable MP4.")
            with gr.Row():
                container = gr.Dropdown(label="Output format", choices=CONTAINER_CHOICES, value="mkv")
                quality = gr.Dropdown(label="Resolution limit", choices=VIDEO_QUALITY_CHOICES, value="source", info="Optional maximum resolution. Compression is controlled by the saved per-format Output Profile in Settings; Auto is recommended.")

        with gr.Row(elem_classes=["dl-magic-actions"]):
            run = gr.Button("Start Processing", variant="primary")
            stop = gr.Button("Stop", variant="secondary", elem_classes=["dl-stop-button"])
        local_files.change(
            fn=_local_queue_status,
            inputs=[local_files],
            outputs=[queue_note, run],
            queue=False,
        )
        stop.click(fn=_stop_processing, queue=False)
        gr.Markdown("Stop ends the current item and remaining queue; completed files stay.", elem_classes=["dl-stop-note"])
        status = gr.Markdown("**Ready** · queue work is sequential.", elem_classes=["dl-stage-status"])

        with gr.Accordion("Output files", open=False):
            with gr.Row():
                source_output = gr.File(label="Source subtitles", file_count="multiple", interactive=False)
                translated_output = gr.File(label="Translated subtitles", file_count="multiple", interactive=False)
            with gr.Row():
                voice_output = gr.File(label="Voice track · WAV", file_count="multiple", interactive=False)
                media_output = gr.File(label="Media output", file_count="multiple", interactive=False)
            queue_table = gr.Dataframe(headers=["#", "Item", "State", "Saved output / error"], datatype=["str", "str", "str", "str"], interactive=False, wrap=True)

        begin = run.click(fn=lambda: "**Processing…** · the progress bar shows the current item and stage.", outputs=[status], queue=False)
        begin.then(
            fn=_run_standard_ui,
            inputs=[source_type, youtube_url, local_files, rights, target, tasks, subtitle_policy, transcription_quality, audio_preferences, container, quality, course_url, lessons, course_state],
            outputs=[source_output, translated_output, voice_output, media_output, queue_table, status],
        )


def _build_advanced() -> None:
    gr.HTML('<div class="dl-main-mode-note"><strong>Advanced workflow</strong> · manual control of source subtitles, translation, voice and export.</div>')
    source_state = gr.State({})
    subtitle_state = gr.State("")
    translated_state = gr.State("")

    with gr.Group():
        source_type = gr.Radio(["YouTube", "Local file"], value="YouTube", label="Source")
        youtube_url = gr.Textbox(label="YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
        local_file = gr.File(label="Local media", file_types=["video", "audio"], type="filepath", visible=False)
        load = gr.Button("Load source", variant="primary")
        source_card = gr.Markdown("**Not loaded** · choose a source and click Load source.", elem_classes=["dl-stage-status"])
        source_type.change(fn=base_ui._toggle_source, inputs=[source_type], outputs=[youtube_url, local_file], queue=False)

    with gr.Accordion("2 · Subtitles", open=False):
        subtitle_track = gr.Dropdown(label="Available subtitles", choices=[], interactive=False)
        caption_note = gr.Markdown("")
        rights = gr.Checkbox(label="I have the right or legal authority to process this media", value=False)
        with gr.Row():
            subtitle_format = gr.Dropdown(label="Download format", choices=SUBTITLE_FORMAT_CHOICES, value="srt")
            extract = gr.Button("Use existing subtitles", variant="primary")
        with gr.Accordion("No usable captions? Transcribe locally with Whisper", open=False):
            with gr.Row():
                whisper_model = gr.Dropdown(label="Whisper model", choices=base_ui.MODEL_CHOICES, value="base")
                spoken_language = gr.Dropdown(label="Spoken language", choices=base_ui.LANGUAGE_CHOICES, value="auto")
            transcribe = gr.Button("Transcribe locally", variant="primary")
        subtitle_status = gr.Markdown("**Waiting** · choose existing captions or transcribe locally.", elem_classes=["dl-stage-status"])
        subtitle_output = gr.File(label="Subtitle download", interactive=False)

    with gr.Accordion("3 · Translate", open=False):
        translation_mode = gr.Dropdown(label="Translation quality", choices=TRANSLATION_MODE_CHOICES, value="contextual")
        with gr.Row():
            from_language = gr.Dropdown(label="From", choices=base_ui.LANGUAGE_CHOICES, value="auto")
            to_language = gr.Dropdown(label="To", choices=base_ui.TARGET_LANGUAGE_CHOICES, value="en")
        translate = gr.Button("Translate subtitles", variant="primary")
        translation_status = gr.Markdown("**Waiting** · prepare a subtitle timeline first.", elem_classes=["dl-stage-status"])
        translated_output = gr.File(label="Translated SRT", interactive=False)
        translated_preview = gr.Dataframe(headers=["Start", "End", "Translation", "Original"], datatype=["str", "str", "str", "str"], interactive=False, wrap=True)

    with gr.Accordion("4 · Voice-over", open=False):
        voice_source = gr.Radio(["Translated subtitles", "Source subtitles"], value="Translated subtitles", label="Voice source")
        voice_lang_choices = voice_language_choices()
        initial_language = "en-US" if any(value == "en-US" for _label, value in voice_lang_choices) else (voice_lang_choices[0][1] if voice_lang_choices else None)
        with gr.Row():
            voice_language = gr.Dropdown(label="Voice language", choices=voice_lang_choices, value=initial_language)
            voice = gr.Dropdown(label="Voice", choices=auto_voice_choices(initial_language), value=auto_default_voice(initial_language))
            speed = gr.Slider(minimum=0.5, maximum=2.0, value=1.0, step=0.05, label="Speed")
        generate = gr.Button("Generate voice track", variant="primary")
        voice_status = gr.Markdown("**Waiting** · choose a subtitle timeline and voice.", elem_classes=["dl-stage-status"])
        voice_audio = gr.Audio(label="Voice preview", type="filepath", interactive=False)
        voice_output = gr.File(label="Voice track · WAV", interactive=False)
        voice_preview = gr.Dataframe(headers=["Start", "End", "Voice duration", "Window fit", "Text"], datatype=["str", "str", "str", "str", "str"], interactive=False, wrap=True)

    with gr.Accordion("5 · Export", open=False):
        with gr.Row():
            audio_mode = gr.Dropdown(label="Audio track", choices=[("Replace primary audio with dub", "replace"), ("Keep original + add dub", "add")], value="replace")
            export_container = gr.Dropdown(label="Container", choices=ADVANCED_CONTAINER_CHOICES, value="mkv")
            export_quality = gr.Dropdown(label="Resolution limit", choices=VIDEO_QUALITY_CHOICES, value="source")
            mix_strategy = gr.Dropdown(label="Audio mix strategy", choices=MIX_STRATEGY_CHOICES, value=advanced_mix_preference())
        with gr.Row():
            render = gr.Button("Create dubbed media", variant="primary")
            package = gr.Button("Package original + subtitles · no dub", variant="secondary")
        export_status = gr.Markdown("**Waiting** · generate a voice track first.", elem_classes=["dl-stage-status"])
        export_output = gr.File(label="Dubbed media", interactive=False)
        package_status = gr.Markdown("**Optional** · original audio/video + source subtitles only.", elem_classes=["dl-stage-status"])
        package_output = gr.File(label="Original media with subtitles", interactive=False)

    activity = gr.Markdown("```text\n[ready] choose a source and load it\n```", elem_classes=["console"])
    subtitle_preview = gr.Dataframe(headers=["Start", "End", "Text"], datatype=["str", "str", "str"], interactive=False, wrap=True)

    scanned = load.click(fn=_advanced_scan, inputs=[source_type, youtube_url, local_file], outputs=[activity, subtitle_track, source_state, subtitle_preview, source_card])
    scanned.then(fn=lambda info, track: base_ui._caption_quality_note(info, track), inputs=[source_state, subtitle_track], outputs=[caption_note], queue=False)
    subtitle_track.change(fn=lambda info, track: base_ui._caption_quality_note(info, track), inputs=[source_state, subtitle_track], outputs=[caption_note], queue=False)

    extract.click(fn=_advanced_extract, inputs=[source_state, subtitle_track, rights, subtitle_format], outputs=[subtitle_output, subtitle_preview, activity, subtitle_state, from_language, subtitle_status])
    transcribe.click(fn=_advanced_transcribe, inputs=[source_state, rights, whisper_model, spoken_language, subtitle_format], outputs=[subtitle_output, subtitle_preview, activity, subtitle_state, from_language, subtitle_status])
    translate.click(fn=_advanced_translate, inputs=[translation_mode, subtitle_state, from_language, to_language, source_state], outputs=[translated_output, translated_preview, activity, translated_state, translation_status])

    voice_language.change(fn=_voice_dropdown, inputs=[voice_language], outputs=[voice], queue=False)
    voice_source.change(fn=_voice_controls, inputs=[voice_source, from_language, to_language], outputs=[voice_language, voice], queue=False)
    from_language.change(fn=_voice_controls, inputs=[voice_source, from_language, to_language], outputs=[voice_language, voice], queue=False)
    to_language.change(fn=_voice_controls, inputs=[voice_source, from_language, to_language], outputs=[voice_language, voice], queue=False)
    generate.click(fn=_advanced_voice, inputs=[voice_source, subtitle_state, translated_state, source_state, voice_language, voice, speed], outputs=[voice_audio, voice_output, voice_preview, activity, voice_status])

    mix_strategy.change(fn=set_advanced_mix_preference, inputs=[mix_strategy], outputs=[], queue=False)
    render.click(fn=_advanced_render, inputs=[source_state, voice_output, rights, voice_language, subtitle_state, translated_state, from_language, to_language, audio_mode, export_container, export_quality, mix_strategy], outputs=[export_output, export_status])
    package.click(fn=_advanced_package, inputs=[source_state, rights, subtitle_state, from_language, export_container, export_quality], outputs=[package_output, package_status])


def _build_settings() -> None:
    gr.HTML(_version_card())
    with gr.Tabs():
        with gr.Tab("Updates"):
            with gr.Group(elem_classes=["dl-update-card"]):
                update_status = gr.Markdown(updater_idle_status())
                update = gr.Button("Update DubLocal", variant="primary")
                gr.HTML('<div class="dl-note">Checks the official main branch, installs a safe update/repair when possible, refreshes the environment and restarts automatically. Local commits and diverged Git history are never overwritten.</div>')
                update.click(fn=update_dublocal_ui, outputs=[update_status])

        with gr.Tab("Model Setup"):
            _build_model_setup_card(first_run=False)

        with gr.Tab("Model Manager"):
            model_action = gr.Markdown("```text\n[model manager] choose an action below\n```", elem_classes=["console"])
            resources = gr.Markdown(local_resource_status(), elem_classes=["console"])
            with gr.Accordion("Whisper · transcription", open=False):
                whisper_status = gr.Markdown(model_manager_status(), elem_classes=["console"])
                whisper_model = gr.Dropdown(label="Whisper model", choices=base_ui.MODEL_CHOICES, value="base")
                with gr.Row():
                    install_whisper = gr.Button("Install / verify model", variant="primary")
                    remove_whisper = gr.Button("Remove model", variant="secondary")
                install_whisper.click(fn=_install_whisper_settings, inputs=[whisper_model], outputs=[whisper_status, resources, model_action])
                remove_whisper.click(fn=_remove_whisper_settings, inputs=[whisper_model], outputs=[whisper_status, resources, model_action])

            with gr.Accordion("Contextual translation", open=False):
                contextual_status = gr.Markdown(adaptive_contextual_translation_status("en", "ru", 0), elem_classes=["console"])
                with gr.Row():
                    prepare_contextual = gr.Button("Prepare / verify contextual translation", variant="primary")
                    remove_contextual = gr.Button("Remove DubLocal contextual model", variant="secondary")
                prepare_contextual.click(fn=_prepare_contextual_settings, outputs=[contextual_status, resources, model_action])
                remove_contextual.click(fn=_remove_contextual_settings, outputs=[contextual_status, resources, model_action])

            with gr.Accordion("Voice engines", open=False):
                voice_status = gr.Markdown(voice_engine_status(), elem_classes=["console"])
                languages = voice_language_choices()
                initial = "en-US" if any(value == "en-US" for _label, value in languages) else languages[0][1]
                with gr.Row():
                    language = gr.Dropdown(label="Voice language", choices=languages, value=initial)
                    voice = gr.Dropdown(label="Voice", choices=voice_choices(initial), value=default_voice(initial))
                language.change(fn=_voice_engine_controls, inputs=[language], outputs=[voice], queue=False)
                prepare_voice = gr.Button("Prepare / verify voice engine", variant="primary")
                prepare_voice.click(fn=_prepare_voice_settings, inputs=[language, voice], outputs=[voice_status, resources, model_action])

            with gr.Accordion("Local TTS providers · Russian & custom models", open=False):
                provider_status = gr.Markdown(provider_status_text(), elem_classes=["console"])
                provider_action = gr.Markdown("```text\n[provider] choose a provider to prepare, or register a custom manifest below\n```", elem_classes=["console"])
                provider_choices = registered_provider_choices()
                provider = gr.Dropdown(label="Registered provider", choices=provider_choices, value=provider_choices[0][1] if provider_choices else None, interactive=bool(provider_choices))
                prepare_provider = gr.Button("Prepare selected provider", variant="secondary")
                prepare_provider.click(fn=prepare_registered_provider_ui, inputs=[provider], outputs=[provider_status, provider_action])
                manifest = gr.Code(label="Custom provider manifest · JSON", value=_EXAMPLE_MANIFEST, language="json", lines=18)
                register = gr.Button("Validate & register custom provider", variant="secondary")
                register.click(fn=_register_provider, inputs=[manifest], outputs=[provider_status, provider_action, provider])

            with gr.Accordion("Vocal separation · music-aware dubbing", open=False):
                separation_status = gr.Markdown(audio_mix_status(), elem_classes=["console"])
                prepare_separation = gr.Button("Prepare vocal separation", variant="secondary")
                prepare_separation.click(fn=prepare_separation_ui, outputs=[separation_status])

            with gr.Accordion("Fast legacy translation · OPUS", open=False):
                gr.Markdown(translation_manager_status("en", "ru"), elem_classes=["console"])
                gr.HTML('<div class="dl-note">Legacy OPUS remains available in Advanced. The recommended Standard workflow uses contextual translation.</div>')

        with gr.Tab("Output Profiles"):
            values = load_profiles()
            gr.HTML('<div class="dl-note"><strong>Auto is format-aware.</strong> MKV preserves source video whenever practical; MP4 targets balanced compatibility; Shareable MP4 targets compact delivery.</div>')
            with gr.Row():
                mkv = gr.Dropdown(label="MKV", choices=PROFILE_CHOICES, value=values["mkv"])
                mp4 = gr.Dropdown(label="MP4", choices=PROFILE_CHOICES, value=values["mp4"])
                share = gr.Dropdown(label="Shareable MP4", choices=PROFILE_CHOICES, value=values["share"])
            profile_status = gr.Markdown(profile_summary(values), elem_classes=["console"])
            with gr.Row():
                save = gr.Button("Save output profiles", variant="primary")
                reset = gr.Button("Restore Auto defaults", variant="secondary")
            save.click(fn=_save_profiles, inputs=[mkv, mp4, share], outputs=[profile_status], queue=False)
            reset.click(fn=_reset_profiles, outputs=[mkv, mp4, share, profile_status], queue=False)

        with gr.Tab("Authenticated Websites"):
            browser_status = gr.Markdown(browser_runtime_status(), elem_classes=["console"])
            with gr.Row():
                prepare_browser = gr.Button("Prepare browser", variant="primary")
                clear_sessions = gr.Button("Clear website sessions", variant="secondary")
            prepare_browser.click(fn=_prepare_browser_ui, outputs=[browser_status])
            clear_sessions.click(fn=_clear_sessions_ui, outputs=[browser_status], queue=False)
            gr.HTML('<div class="dl-note">Sign-in sessions stay local. DubLocal refuses DRM-protected media and does not bypass access controls.</div>')

        with gr.Tab("Storage & Cleanup"):
            storage_status = gr.Markdown(storage_status_markdown(), elem_classes=["console"])
            with gr.Row():
                refresh = gr.Button("Refresh storage usage", variant="secondary")
                clean = gr.Button("Clean temporary files", variant="primary")
            refresh.click(fn=storage_status_markdown, outputs=[storage_status], queue=False)
            clean.click(fn=clean_temporary_files_status, outputs=[storage_status], queue=False)
            gr.HTML('<div class="dl-note">Cleanup removes temporary jobs/cache only. Installed models, website sessions, course resume state and finished outputs are protected.</div>')

        with gr.Tab("Local Resources"):
            status = gr.Markdown(local_resource_status(), elem_classes=["console"])
            refresh = gr.Button("Rescan local resources", variant="secondary")
            refresh.click(fn=local_resource_status, outputs=[status], queue=False)


def build_app() -> gr.Blocks:
    """Build the production application explicitly; no constructor or callback replacement."""

    with gr.Blocks(title="DubLocal_") as demo:
        gr.HTML(_header())
        with gr.Tabs():
            with gr.Tab("Main"):
                with gr.Tabs():
                    with gr.Tab("Standard"):
                        _build_standard()
                    with gr.Tab("Advanced"):
                        _build_advanced()
            with gr.Tab("Settings"):
                _build_settings()

    unload = getattr(demo, "unload", None)
    if callable(unload):
        unload(fn=release_session_resources)
    return demo
