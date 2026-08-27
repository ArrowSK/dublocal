from __future__ import annotations

import gradio as gr

from . import __version__
from .app import (
    LANGUAGE_CHOICES,
    MATRIX_CSS as BASE_CSS,
    MODEL_CHOICES,
    TARGET_LANGUAGE_CHOICES,
    _error_status,
    _toggle_source,
    check_updates_ui,
    extract_selected,
    install_update_ui,
    prepare_translation_ui,
    refresh_resources_ui,
    remove_selected_model,
    remove_translation_models_ui,
    repair_installation_ui,
    restart_ui,
    scan_source,
    transcribe_selected,
    translate_selected,
)
from .contextual_progress import translate_srt_contextual_with_progress
from .contextual_translation import (
    contextual_translation_status,
    prepare_contextual_translation,
    remove_contextual_model,
)
from .dependencies import local_resource_status
from .progress import ProgressEstimator
from .progress_operations import (
    generate_voice_track_with_progress,
    install_whisper_model_with_progress,
)
from .transcription import model_manager_status
from .translation import translated_segments_to_rows, translation_manager_status
from .tts import (
    KOKORO_LANGUAGE_CHOICES,
    kokoro_default_voice,
    kokoro_runtime_status,
    kokoro_voice_choices,
    prepare_kokoro,
    suggested_kokoro_language,
    voice_segments_to_rows,
)


MATRIX_CSS = BASE_CSS + r"""
:root {
  --primary-50: #effff5 !important;
  --primary-100: #d8ffe6 !important;
  --primary-200: #aafcc6 !important;
  --primary-300: #78f4a4 !important;
  --primary-400: #42ef83 !important;
  --primary-500: #42ef83 !important;
  --primary-600: #2bd26d !important;
  --primary-700: #20aa57 !important;
  --primary-800: #198646 !important;
  --primary-900: #126638 !important;
  --color-accent: #42ef83 !important;
  accent-color: #42ef83 !important;
}

button[role="tab"][aria-selected="true"],
button.selected,
.tab-nav button.selected,
.tabs button.selected {
  color: var(--dl-green) !important;
  border-color: var(--dl-green) !important;
  box-shadow: inset 0 -2px 0 var(--dl-green) !important;
}

button[role="tab"]:hover,
.tab-nav button:hover,
.tabs button:hover {
  color: var(--dl-green-soft) !important;
}

input[type="range"], progress {
  accent-color: var(--dl-green) !important;
}

.dl-version-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 8px 0 18px 0;
  padding: 12px 14px;
  border: 1px solid var(--dl-border);
  border-radius: 10px;
  background: rgba(8, 18, 12, 0.72);
}

.dl-version-number {
  color: var(--dl-green);
  font: 700 14px ui-monospace, SFMono-Regular, Menlo, monospace;
}

.dl-flow {
  margin: 4px 0 14px 0;
  color: var(--dl-muted);
  font-size: 13px;
}

.dl-flow strong { color: var(--dl-green-soft); }

.dl-compact-note {
  color: var(--dl-muted);
  font-size: 12px;
  margin: 4px 0 8px 0;
}

.console { min-height: 72px !important; }
"""


TRANSLATION_MODE_CHOICES = [
    ("Contextual quality · Qwen3 4B · recommended", "contextual"),
    ("Fast legacy · OPUS · sentence-level", "opus"),
]

TRANSLATION_ROUTE_CHOICES = [
    ("English → supported languages · ~310 MiB", "en-to-many"),
    ("Supported languages → English · ~310 MiB", "many-to-en"),
    ("Non-English ↔ non-English · both models · ~620 MiB", "both"),
]


def _progress_callback(progress: gr.Progress):
    estimator = ProgressEstimator()

    def update(fraction: float, label: str) -> None:
        progress(fraction, desc=estimator.message(fraction, label))

    return update


def _translation_route_languages(route: str) -> tuple[str, str]:
    if route == "many-to-en":
        return "hu", "en"
    if route == "both":
        return "hu", "de"
    return "en", "hu"


def _translation_route_status(route: str) -> str:
    source, target = _translation_route_languages(route)
    return translation_manager_status(source, target)


def _media_duration_ms(source_info: dict | None) -> int:
    try:
        seconds = float((source_info or {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        seconds = 0.0
    return max(0, int(seconds * 1000))


def _translation_status_for_ui(
    mode: str,
    source_language: str,
    target_language: str,
    source_info: dict | None,
) -> str:
    try:
        if mode == "opus":
            return translation_manager_status(source_language, target_language)
        return contextual_translation_status(
            source_language,
            target_language,
            _media_duration_ms(source_info),
        )
    except Exception as exc:
        return _error_status(str(exc))


def _scan_source_ui(
    source_type: str,
    youtube_url: str,
    local_file: str | None,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress_callback(progress)
    update(0.05, "Inspecting source")
    result = scan_source(source_type, youtube_url, local_file)
    update(1.0, "Source ready")
    return result


def _extract_ui(
    info: dict,
    track_value: str | None,
    rights_confirmed: bool,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress_callback(progress)
    update(0.08, "Extracting subtitle track")
    result = extract_selected(info, track_value, rights_confirmed)
    update(1.0, "Subtitle timeline ready")
    return result


def _transcribe_ui(
    info: dict,
    rights_confirmed: bool,
    model_id: str,
    language: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress_callback(progress)
    update(0.04, "Preparing local transcription")
    result = transcribe_selected(info, rights_confirmed, model_id, language)
    update(1.0, "Transcription complete")
    return result


def _install_whisper_settings(
    model_id: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress_callback(progress)
    try:
        path = install_whisper_model_with_progress(model_id, progress_callback=update)
        action = (
            "```text\n"
            f"[done] Whisper {model_id} installed and checksum verified\n"
            f"[model] {path.name}\n"
            "```"
        )
    except Exception as exc:
        action = _error_status(str(exc))
    status = model_manager_status()
    return status, status, action


def _remove_whisper_settings(model_id: str):
    status, action = remove_selected_model(model_id)
    return status, status, action


def _prepare_translation_settings(
    route: str,
    main_mode: str,
    main_source_language: str,
    main_target_language: str,
    source_info: dict | None,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress_callback(progress)
    update(0.03, "Preparing legacy translation runtime/models")
    source, target = _translation_route_languages(route)
    settings_status, action = prepare_translation_ui(source, target)
    update(1.0, "Legacy translation ready")
    main_status = _translation_status_for_ui(
        main_mode, main_source_language, main_target_language, source_info
    )
    return settings_status, main_status, action


def _remove_translation_settings(
    route: str,
    main_mode: str,
    main_source_language: str,
    main_target_language: str,
    source_info: dict | None,
):
    source, target = _translation_route_languages(route)
    settings_status, action = remove_translation_models_ui(source, target)
    main_status = _translation_status_for_ui(
        main_mode, main_source_language, main_target_language, source_info
    )
    return settings_status, main_status, action


def _prepare_contextual_settings(
    main_mode: str,
    main_source_language: str,
    main_target_language: str,
    source_info: dict | None,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress_callback(progress)
    try:
        update(0.02, "Checking llama.cpp and contextual model")
        prepared = prepare_contextual_translation()
        update(1.0, "Contextual translation ready")
        action = (
            "```text\n"
            "[done] contextual translation is ready\n"
            f"[runtime/model] {prepared}\n"
            "[engine] Qwen3 4B Q4_K_M through llama.cpp\n"
            "```"
        )
    except Exception as exc:
        action = _error_status(str(exc))
    settings_status = contextual_translation_status("en", "ru", 0)
    main_status = _translation_status_for_ui(
        main_mode, main_source_language, main_target_language, source_info
    )
    return settings_status, main_status, local_resource_status(), action


def _remove_contextual_settings(
    main_mode: str,
    main_source_language: str,
    main_target_language: str,
    source_info: dict | None,
):
    try:
        removed = remove_contextual_model()
        action = (
            "```text\n"
            f"[model] contextual Qwen3 registration {'removed' if removed else 'was not installed'}\n"
            "[shared cache] shared Hugging Face files are kept\n"
            "```"
        )
    except Exception as exc:
        action = _error_status(str(exc))
    settings_status = contextual_translation_status("en", "ru", 0)
    main_status = _translation_status_for_ui(
        main_mode, main_source_language, main_target_language, source_info
    )
    return settings_status, main_status, local_resource_status(), action


def _voice_dropdown(language: str | None):
    choices = kokoro_voice_choices(language)
    value = kokoro_default_voice(language)
    return gr.Dropdown(choices=choices, value=value, interactive=bool(choices))


def _suggest_voice_controls(
    timeline_source: str,
    source_language: str,
    target_language: str,
):
    language = source_language if timeline_source == "Source subtitles" else target_language
    suggested = suggested_kokoro_language(language)
    if suggested is None:
        return gr.Dropdown(value=None), gr.Dropdown(choices=[], value=None, interactive=False)
    return gr.Dropdown(value=suggested), _voice_dropdown(suggested)


def _translation_preview_rows(rows: list[list[str]]) -> list[list[str]]:
    return [
        [row[0], row[1], row[3], row[2]] if len(row) >= 4 else list(row)
        for row in rows
    ]


def _translation_result_note(rows: list[list[str]]) -> str:
    comparable = [row for row in rows if len(row) >= 4]
    changed = sum(1 for row in comparable if str(row[2]).strip() != str(row[3]).strip())
    return f"[translation] {changed}/{len(comparable)} segment(s) differ from the source"


def _translate_with_state(
    mode: str,
    subtitle_path: str,
    source_language: str,
    target_language: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    if not subtitle_path:
        return None, [], _error_status(
            "Extract or transcribe subtitles first. Translation reuses that timed SRT."
        ), ""

    update = _progress_callback(progress)
    if mode == "opus":
        update(0.05, "Running fast legacy translation")
        output, rows, status = translate_selected(subtitle_path, source_language, target_language)
        update(1.0, "Translation complete")
    else:
        try:
            result = translate_srt_contextual_with_progress(
                subtitle_path,
                source_language,
                target_language,
                progress_callback=update,
            )
            output = str(result.srt_path)
            rows = translated_segments_to_rows(result.segments)
            status = (
                "```text\n"
                "[done] contextual subtitle translation complete\n"
                f"[route] {result.route}\n"
                f"[segments] {len(result.segments)} · original timings preserved\n"
                "[quality] surrounding source context + rolling prior translations were used\n"
                f"[output] {result.srt_path.name}\n"
                "```"
            )
        except Exception as exc:
            return None, [], _error_status(str(exc)), ""

    if output and rows:
        note = _translation_result_note(rows)
        status = status.replace("\n```", f"\n{note}\n```", 1)
    return output, _translation_preview_rows(rows), status, output or ""


def _generate_voice_ui(
    timeline_source: str,
    source_subtitle_path: str,
    translated_subtitle_path: str,
    language: str | None,
    voice: str | None,
    speed: float,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    selected = source_subtitle_path if timeline_source == "Source subtitles" else translated_subtitle_path
    if not selected:
        missing = (
            "Extract or transcribe source subtitles first."
            if timeline_source == "Source subtitles"
            else "Translate subtitles first, or switch Voice source to Source subtitles."
        )
        return None, None, [], _error_status(missing)
    if not language or not voice:
        return None, None, [], _error_status(
            "Official Kokoro does not support the selected subtitle language, or no compatible voice is selected."
        )

    update = _progress_callback(progress)
    try:
        result = generate_voice_track_with_progress(
            selected,
            language=language,
            voice=voice,
            speed=float(speed),
            progress_callback=update,
        )
        overflow_count = sum(1 for item in result.segments if item.overflow_ms > 0)
        overflow_note = (
            f"{overflow_count} segment(s) exceed their subtitle window"
            if overflow_count
            else "all generated segments fit inside their current subtitle windows"
        )
        status = (
            "```text\n"
            "[done] local Kokoro voice generation complete\n"
            f"[runtime] {result.runtime_label} · {result.device}\n"
            f"[voice] {result.language} · {result.voice} · speed {result.speed:.2f}\n"
            f"[segments] {len(result.segments)}\n"
            f"[timing] {overflow_note}\n"
            f"[output] {result.wav_path.name}\n"
            "```"
        )
        rows = voice_segments_to_rows(result.segments)
        path = str(result.wav_path)
        return path, path, rows, status
    except Exception as exc:
        return None, None, [], _error_status(str(exc))


def _prepare_kokoro_settings(
    language: str,
    voice: str,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
):
    update = _progress_callback(progress)
    try:
        update(0.05, "Preparing Kokoro runtime and voice assets")
        runtime = prepare_kokoro(language, voice, 1.0)
        update(1.0, "Kokoro ready")
        action = (
            "```text\n"
            "[done] Kokoro is ready\n"
            f"[runtime] {runtime}\n"
            "```"
        )
    except Exception as exc:
        action = _error_status(str(exc))
    return kokoro_runtime_status(), local_resource_status(), action


def _settings_version_html() -> str:
    return (
        '<div class="dl-version-card">'
        '<div><strong>DubLocal</strong><div class="dl-note">Running local development build</div></div>'
        f'<div class="dl-version-number">v{__version__}</div>'
        '</div>'
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="DubLocal_") as demo:
        gr.HTML(
            """
            <div class="dl-header">
              <div class="dl-brand">DubLocal<span class="dl-cursor">_</span><span class="dl-local">LOCAL</span></div>
              <div class="dl-subtitle">Subtitles, contextual translation and local AI voice-over — processed on your Mac.</div>
            </div>
            """
        )

        source_state = gr.State({})
        subtitle_path_state = gr.State("")
        translated_path_state = gr.State("")

        with gr.Tabs():
            with gr.Tab("Main"):
                gr.HTML(
                    '<div class="dl-flow"><strong>1 Source</strong> → 2 Subtitles → 3 Translate → 4 Voice-over. '
                    'Open only the stage you need.</div>'
                )

                with gr.Group():
                    with gr.Row():
                        source_type = gr.Radio(
                            ["YouTube", "Local file"], value="YouTube", label="Source"
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
                    scan_button = gr.Button("Load source", variant="primary")

                with gr.Accordion("2 · Subtitles", open=False):
                    subtitle_track = gr.Dropdown(
                        label="Existing subtitle / caption track",
                        choices=[],
                        interactive=False,
                    )
                    rights = gr.Checkbox(
                        label="I have the right or legal authority to process this media",
                        value=False,
                    )
                    extract_button = gr.Button("Use existing subtitles", variant="primary")
                    with gr.Accordion("No usable captions? Transcribe locally with Whisper", open=False):
                        with gr.Row():
                            whisper_model_main = gr.Dropdown(
                                label="Whisper model", choices=MODEL_CHOICES, value="base"
                            )
                            source_language = gr.Dropdown(
                                label="Spoken language", choices=LANGUAGE_CHOICES, value="auto"
                            )
                        transcribe_button = gr.Button("Transcribe locally", variant="primary")
                        gr.HTML(
                            '<div class="dl-compact-note">Model install/remove lives in Settings → Model Manager.</div>'
                        )

                with gr.Accordion("3 · Translate", open=False):
                    translation_mode = gr.Dropdown(
                        choices=TRANSLATION_MODE_CHOICES,
                        value="contextual",
                        label="Translation quality",
                    )
                    with gr.Row():
                        translation_source_language = gr.Dropdown(
                            label="From", choices=LANGUAGE_CHOICES, value="auto"
                        )
                        translation_target_language = gr.Dropdown(
                            label="To", choices=TARGET_LANGUAGE_CHOICES, value="en"
                        )
                    translate_button = gr.Button("Translate subtitles", variant="primary")
                    with gr.Accordion("Translation engine details", open=False):
                        translation_status_main = gr.Markdown(
                            contextual_translation_status("auto", "en", 0),
                            elem_classes=["console"],
                        )
                    translated_output = gr.File(label="Translated SRT", interactive=False)
                    translated_preview = gr.Dataframe(
                        headers=["Start", "End", "Translation", "Original"],
                        datatype=["str", "str", "str", "str"],
                        column_widths=["105px", "105px", "40%", "40%"],
                        value=[],
                        interactive=False,
                        wrap=True,
                        label="Translated subtitle preview",
                    )

                with gr.Accordion("4 · Voice-over", open=False):
                    voice_source = gr.Radio(
                        ["Translated subtitles", "Source subtitles"],
                        value="Translated subtitles",
                        label="Voice source",
                    )
                    with gr.Row():
                        tts_language = gr.Dropdown(
                            label="Voice language",
                            choices=KOKORO_LANGUAGE_CHOICES,
                            value="en-US",
                        )
                        tts_voice = gr.Dropdown(
                            label="Voice",
                            choices=kokoro_voice_choices("en-US"),
                            value=kokoro_default_voice("en-US"),
                        )
                        tts_speed = gr.Slider(
                            minimum=0.5,
                            maximum=2.0,
                            value=1.0,
                            step=0.05,
                            label="Speed",
                        )
                    generate_voice_button = gr.Button("Generate voice track", variant="primary")
                    voice_audio = gr.Audio(
                        label="Voice preview", type="filepath", interactive=False
                    )
                    voice_output = gr.File(label="Voice-only WAV", interactive=False)
                    with gr.Accordion("Voice timing details", open=False):
                        voice_preview = gr.Dataframe(
                            headers=["Start", "End", "Voice duration", "Window fit", "Text"],
                            datatype=["str", "str", "str", "str", "str"],
                            value=[],
                            interactive=False,
                            wrap=True,
                        )

                with gr.Accordion("Results & activity details", open=False):
                    status = gr.Markdown(
                        "```text\n[ready] choose a source and load it\n```",
                        elem_classes=["console"],
                    )
                    subtitle_output = gr.File(label="Source subtitle output", interactive=False)
                    subtitle_preview = gr.Dataframe(
                        headers=["Start", "End", "Text"],
                        datatype=["str", "str", "str"],
                        value=[],
                        interactive=False,
                        wrap=True,
                        label="Timed source subtitle preview",
                    )

            with gr.Tab("Settings"):
                gr.HTML(_settings_version_html())
                with gr.Tabs():
                    with gr.Tab("Updates"):
                        update_status = gr.Markdown(
                            "```text\n[updates] Check official GitHub main, install clean fast-forwards or repair the local installation\n```",
                            elem_classes=["console"],
                        )
                        repair_confirm = gr.Checkbox(
                            label="Allow Repair installation to replace modified tracked DubLocal files after saving a patch backup",
                            value=False,
                        )
                        with gr.Row():
                            check_update_button = gr.Button("Check for updates", variant="secondary")
                            install_update_button = gr.Button("Install update", variant="secondary")
                            repair_button = gr.Button("Repair installation", variant="secondary")
                            restart_button = gr.Button("Restart DubLocal", variant="primary")

                    with gr.Tab("Model Manager"):
                        gr.HTML(
                            '<div class="dl-compact-note">Install optional AI resources only when you need them. Existing compatible local tools/caches are reused first.</div>'
                        )
                        with gr.Accordion("Whisper · transcription", open=False):
                            whisper_settings_status = gr.Markdown(
                                model_manager_status(), elem_classes=["console"]
                            )
                            whisper_model_settings = gr.Dropdown(
                                label="Whisper model", choices=MODEL_CHOICES, value="base"
                            )
                            with gr.Row():
                                install_whisper_button = gr.Button("Install / verify model", variant="primary")
                                remove_whisper_button = gr.Button("Remove model", variant="secondary")

                        with gr.Accordion("Contextual translation · Qwen3 4B", open=False):
                            contextual_settings_status = gr.Markdown(
                                contextual_translation_status("en", "ru", 0),
                                elem_classes=["console"],
                            )
                            with gr.Row():
                                prepare_contextual_button = gr.Button(
                                    "Prepare / verify contextual translation", variant="primary"
                                )
                                remove_contextual_button = gr.Button(
                                    "Remove DubLocal contextual model", variant="secondary"
                                )

                        with gr.Accordion("Fast legacy translation · OPUS", open=False):
                            translation_route = gr.Dropdown(
                                label="Legacy translation model set",
                                choices=TRANSLATION_ROUTE_CHOICES,
                                value="en-to-many",
                            )
                            translation_settings_status = gr.Markdown(
                                _translation_route_status("en-to-many"), elem_classes=["console"]
                            )
                            with gr.Row():
                                install_translation_button = gr.Button(
                                    "Install / verify legacy model(s)", variant="secondary"
                                )
                                remove_translation_button = gr.Button(
                                    "Remove legacy translation models", variant="secondary"
                                )

                        with gr.Accordion("Kokoro · voice generation", open=False):
                            kokoro_settings_status = gr.Markdown(
                                kokoro_runtime_status(), elem_classes=["console"]
                            )
                            with gr.Row():
                                kokoro_language_settings = gr.Dropdown(
                                    label="Prepare language",
                                    choices=KOKORO_LANGUAGE_CHOICES,
                                    value="en-US",
                                )
                                kokoro_voice_settings = gr.Dropdown(
                                    label="Prepare voice",
                                    choices=kokoro_voice_choices("en-US"),
                                    value=kokoro_default_voice("en-US"),
                                )
                            prepare_kokoro_button = gr.Button(
                                "Prepare / verify Kokoro", variant="primary"
                            )

                        model_action = gr.Markdown(
                            "```text\n[model manager] choose a model action above\n```",
                            elem_classes=["console"],
                        )

                    with gr.Tab("Local Resources"):
                        resource_status = gr.Markdown(
                            local_resource_status(), elem_classes=["console"]
                        )
                        refresh_resources_button = gr.Button("Rescan local resources", variant="secondary")

        source_type.change(
            fn=_toggle_source,
            inputs=[source_type],
            outputs=[youtube_url, local_file],
            queue=False,
        )
        scan_event = scan_button.click(
            fn=_scan_source_ui,
            inputs=[source_type, youtube_url, local_file],
            outputs=[status, subtitle_track, source_state, subtitle_preview],
        )
        scan_event.then(
            fn=_translation_status_for_ui,
            inputs=[translation_mode, translation_source_language, translation_target_language, source_state],
            outputs=[translation_status_main],
            queue=False,
        )
        extract_button.click(
            fn=_extract_ui,
            inputs=[source_state, subtitle_track, rights],
            outputs=[subtitle_output, subtitle_preview, status, subtitle_path_state, translation_source_language],
        )
        transcribe_button.click(
            fn=_transcribe_ui,
            inputs=[source_state, rights, whisper_model_main, source_language],
            outputs=[subtitle_output, subtitle_preview, status, subtitle_path_state, translation_source_language],
        )

        for component in (translation_mode, translation_source_language, translation_target_language):
            component.change(
                fn=_translation_status_for_ui,
                inputs=[translation_mode, translation_source_language, translation_target_language, source_state],
                outputs=[translation_status_main],
                queue=False,
            )

        translate_button.click(
            fn=_translate_with_state,
            inputs=[translation_mode, subtitle_path_state, translation_source_language, translation_target_language],
            outputs=[translated_output, translated_preview, status, translated_path_state],
        )

        voice_source.change(
            fn=_suggest_voice_controls,
            inputs=[voice_source, translation_source_language, translation_target_language],
            outputs=[tts_language, tts_voice],
            queue=False,
        )
        translation_source_language.change(
            fn=_suggest_voice_controls,
            inputs=[voice_source, translation_source_language, translation_target_language],
            outputs=[tts_language, tts_voice],
            queue=False,
        )
        translation_target_language.change(
            fn=_suggest_voice_controls,
            inputs=[voice_source, translation_source_language, translation_target_language],
            outputs=[tts_language, tts_voice],
            queue=False,
        )
        tts_language.change(fn=_voice_dropdown, inputs=[tts_language], outputs=[tts_voice], queue=False)
        generate_voice_button.click(
            fn=_generate_voice_ui,
            inputs=[voice_source, subtitle_path_state, translated_path_state, tts_language, tts_voice, tts_speed],
            outputs=[voice_audio, voice_output, voice_preview, status],
        )

        whisper_model_main.change(
            fn=lambda value: value,
            inputs=[whisper_model_main],
            outputs=[whisper_model_settings],
            queue=False,
        )
        whisper_model_settings.change(
            fn=lambda value: value,
            inputs=[whisper_model_settings],
            outputs=[whisper_model_main],
            queue=False,
        )
        install_whisper_button.click(
            fn=_install_whisper_settings,
            inputs=[whisper_model_settings],
            outputs=[whisper_settings_status, gr.State(), model_action],
        )
        remove_whisper_button.click(
            fn=_remove_whisper_settings,
            inputs=[whisper_model_settings],
            outputs=[whisper_settings_status, gr.State(), model_action],
        )

        prepare_contextual_button.click(
            fn=_prepare_contextual_settings,
            inputs=[translation_mode, translation_source_language, translation_target_language, source_state],
            outputs=[contextual_settings_status, translation_status_main, resource_status, model_action],
        )
        remove_contextual_button.click(
            fn=_remove_contextual_settings,
            inputs=[translation_mode, translation_source_language, translation_target_language, source_state],
            outputs=[contextual_settings_status, translation_status_main, resource_status, model_action],
        )

        translation_route.change(
            fn=_translation_route_status,
            inputs=[translation_route],
            outputs=[translation_settings_status],
            queue=False,
        )
        install_translation_button.click(
            fn=_prepare_translation_settings,
            inputs=[translation_route, translation_mode, translation_source_language, translation_target_language, source_state],
            outputs=[translation_settings_status, translation_status_main, model_action],
        )
        remove_translation_button.click(
            fn=_remove_translation_settings,
            inputs=[translation_route, translation_mode, translation_source_language, translation_target_language, source_state],
            outputs=[translation_settings_status, translation_status_main, model_action],
        )

        kokoro_language_settings.change(
            fn=_voice_dropdown,
            inputs=[kokoro_language_settings],
            outputs=[kokoro_voice_settings],
            queue=False,
        )
        prepare_kokoro_button.click(
            fn=_prepare_kokoro_settings,
            inputs=[kokoro_language_settings, kokoro_voice_settings],
            outputs=[kokoro_settings_status, resource_status, model_action],
        )

        refresh_resources_button.click(fn=refresh_resources_ui, outputs=[resource_status])
        check_update_button.click(fn=check_updates_ui, outputs=[update_status])
        install_update_button.click(fn=install_update_ui, outputs=[update_status])
        repair_button.click(
            fn=repair_installation_ui,
            inputs=[repair_confirm],
            outputs=[update_status],
        )
        restart_button.click(fn=restart_ui, outputs=[update_status])

    return demo
