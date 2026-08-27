from __future__ import annotations

import gradio as gr

from .app import (
    LANGUAGE_CHOICES,
    MATRIX_CSS,
    MODEL_CHOICES,
    TARGET_LANGUAGE_CHOICES,
    _error_status,
    _toggle_source,
    check_updates_ui,
    extract_selected,
    install_selected_model,
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
from .contextual_translation import (
    contextual_translation_status,
    prepare_contextual_translation,
    remove_contextual_model,
    translate_srt_contextual,
)
from .dependencies import local_resource_status
from .transcription import model_manager_status
from .translation import translated_segments_to_rows, translation_manager_status
from .tts import (
    KOKORO_LANGUAGE_CHOICES,
    generate_voice_track,
    kokoro_default_voice,
    kokoro_runtime_status,
    kokoro_voice_choices,
    prepare_kokoro,
    suggested_kokoro_language,
    voice_segments_to_rows,
)


TRANSLATION_MODE_CHOICES = [
    ("Contextual quality · Qwen3 4B · recommended", "contextual"),
    ("Fast legacy · OPUS · sentence-level", "opus"),
]

TRANSLATION_ROUTE_CHOICES = [
    ("English → supported languages · ~310 MiB", "en-to-many"),
    ("Supported languages → English · ~310 MiB", "many-to-en"),
    ("Non-English ↔ non-English · both models · ~620 MiB", "both"),
]


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


def _install_whisper_settings(model_id: str):
    status, action = install_selected_model(model_id)
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
):
    source, target = _translation_route_languages(route)
    settings_status, action = prepare_translation_ui(source, target)
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
):
    try:
        prepared = prepare_contextual_translation()
        action = (
            "```text\n"
            "[done] contextual translation is ready\n"
            f"[runtime/model] {prepared}\n"
            "[engine] Qwen3 4B Q4_K_M through llama.cpp\n"
            "[context] surrounding source + rolling prior translations; budget grows with video duration\n"
            "[next] use Main → Local translation with Contextual quality selected\n"
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
            "[shared cache] Hugging Face cache is kept so other local apps are not broken\n"
            "[runtime] llama.cpp is kept because it may be reused elsewhere\n"
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
    return gr.Dropdown(
        choices=choices,
        value=value,
        interactive=bool(choices),
    )


def _suggest_voice_controls(
    timeline_source: str,
    source_language: str,
    target_language: str,
):
    language = source_language if timeline_source == "Source subtitles" else target_language
    suggested = suggested_kokoro_language(language)
    if suggested is None:
        return (
            gr.Dropdown(value=None),
            gr.Dropdown(choices=[], value=None, interactive=False),
        )
    return gr.Dropdown(value=suggested), _voice_dropdown(suggested)


def _translation_preview_rows(rows: list[list[str]]) -> list[list[str]]:
    """Put translated text before source text so it stays visible on normal-width windows."""

    return [
        [row[0], row[1], row[3], row[2]] if len(row) >= 4 else list(row)
        for row in rows
    ]


def _translation_result_note(rows: list[list[str]]) -> str:
    comparable = [row for row in rows if len(row) >= 4]
    changed = sum(
        1
        for row in comparable
        if str(row[2]).strip() != str(row[3]).strip()
    )
    return f"[translation] {changed}/{len(comparable)} segment(s) differ from the source"


def _translate_with_state(
    mode: str,
    subtitle_path: str,
    source_language: str,
    target_language: str,
):
    if not subtitle_path:
        return None, [], _error_status(
            "Extract or transcribe subtitles first. Translation reuses that timed SRT."
        ), ""

    if mode == "opus":
        output, rows, status = translate_selected(
            subtitle_path, source_language, target_language
        )
    else:
        try:
            result = translate_srt_contextual(
                subtitle_path,
                source_language,
                target_language,
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
                "[next] review the translated preview, then generate a voice track if the target language has a TTS backend\n"
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
):
    selected = (
        source_subtitle_path
        if timeline_source == "Source subtitles"
        else translated_subtitle_path
    )
    if not selected:
        missing = (
            "Extract or transcribe source subtitles first."
            if timeline_source == "Source subtitles"
            else "Translate subtitles first, or switch Voice source to Source subtitles."
        )
        return None, None, [], _error_status(missing)
    if not language or not voice:
        return None, None, [], _error_status(
            "Official Kokoro does not support the selected subtitle language, or no compatible voice is selected. "
            "Choose a supported Kokoro language/voice or keep the subtitle-only output."
        )

    try:
        result = generate_voice_track(
            selected,
            language=language,
            voice=voice,
            speed=float(speed),
        )
        overflow_count = sum(1 for item in result.segments if item.overflow_ms > 0)
        overflow_note = (
            f"{overflow_count} segment(s) exceed their subtitle window; M5 will add duration fitting"
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
            "[scope] M4 output is voice-only; original-audio ducking/mixing and stream-copy media export arrive in M5\n"
            "```"
        )
        rows = voice_segments_to_rows(result.segments)
        path = str(result.wav_path)
        return path, path, rows, status
    except Exception as exc:
        return None, None, [], _error_status(str(exc))


def _prepare_kokoro_settings(language: str, voice: str):
    try:
        runtime = prepare_kokoro(language, voice, 1.0)
        action = (
            "```text\n"
            "[done] Kokoro is ready\n"
            f"[runtime] {runtime}\n"
            "[model] official Kokoro-82M/voice assets verified through the shared Hugging Face cache\n"
            "[next] use Main → Local voice · Kokoro\n"
            "```"
        )
    except Exception as exc:
        action = _error_status(str(exc))
    return kokoro_runtime_status(), local_resource_status(), action


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
                with gr.Group():
                    source_type = gr.Radio(
                        ["YouTube", "Local file"],
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
                    scan_button = gr.Button("Scan source", variant="primary")

                with gr.Group():
                    subtitle_track = gr.Dropdown(
                        label="Existing subtitle / caption track",
                        choices=[],
                        interactive=False,
                    )
                    rights = gr.Checkbox(
                        label="I have the right or legal authority to process this media",
                        value=False,
                    )
                    extract_button = gr.Button("Extract existing subtitles", variant="secondary")

                with gr.Accordion("Local transcription · Whisper", open=True):
                    model_status_main = gr.Markdown(model_manager_status(), elem_classes=["console"])
                    with gr.Row():
                        whisper_model_main = gr.Dropdown(
                            label="Whisper model",
                            choices=MODEL_CHOICES,
                            value="base",
                        )
                        source_language = gr.Dropdown(
                            label="Spoken language",
                            choices=LANGUAGE_CHOICES,
                            value="auto",
                        )
                    transcribe_button = gr.Button("Transcribe locally", variant="primary")
                    gr.HTML(
                        """
                        <div class="dl-note">
                          Whisper model installation and removal live in <strong>Settings → Model Manager</strong>.
                        </div>
                        """
                    )

                status = gr.Markdown(
                    "```text\n[ready] choose a source and scan it\n[mode] M4 + M3.1 · captions + transcription + contextual translation + Kokoro voice\n```",
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

                with gr.Accordion("Local translation", open=True):
                    translation_mode = gr.Radio(
                        choices=TRANSLATION_MODE_CHOICES,
                        value="contextual",
                        label="Translation quality",
                    )
                    with gr.Row():
                        translation_source_language = gr.Dropdown(
                            label="Subtitle language",
                            choices=LANGUAGE_CHOICES,
                            value="auto",
                        )
                        translation_target_language = gr.Dropdown(
                            label="Translate to",
                            choices=TARGET_LANGUAGE_CHOICES,
                            value="en",
                        )
                    translation_status_main = gr.Markdown(
                        contextual_translation_status("auto", "en", 0),
                        elem_classes=["console"],
                    )
                    translate_button = gr.Button("Translate subtitles", variant="primary")
                    gr.HTML(
                        """
                        <div class="dl-note">
                          <strong>Contextual quality</strong> is the default. It translates groups of subtitles with nearby
                          source dialogue, programme-wide reference lines and recent translated lines. The context budget grows
                          automatically with video duration. <strong>Fast legacy</strong> keeps the older sentence-level OPUS
                          path only when you explicitly choose it. Prepare models in <strong>Settings → Model Manager</strong>.
                        </div>
                        """
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

                with gr.Accordion("Local voice · Kokoro", open=True):
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
                            label="Kokoro voice",
                            choices=kokoro_voice_choices("en-US"),
                            value=kokoro_default_voice("en-US"),
                        )
                        tts_speed = gr.Slider(
                            minimum=0.5,
                            maximum=2.0,
                            value=1.0,
                            step=0.05,
                            label="Voice speed",
                        )
                    generate_voice_button = gr.Button("Generate voice track", variant="primary")
                    gr.HTML(
                        """
                        <div class="dl-note">
                          M4 generates a synchronized <strong>voice-only WAV</strong> from the selected SRT and keeps every
                          subtitle start time. It does not yet modify the movie soundtrack. Official Kokoro currently covers
                          American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin.
                          Hungarian, Russian, German and other unsupported targets remain subtitle-only until another local TTS
                          backend is added. Prepare Kokoro under <strong>Settings → Model Manager</strong> first.
                        </div>
                        """
                    )
                    voice_audio = gr.Audio(
                        label="Voice-only preview",
                        type="filepath",
                        interactive=False,
                    )
                    voice_output = gr.File(label="Voice-only WAV", interactive=False)
                    voice_preview = gr.Dataframe(
                        headers=["Start", "End", "Voice duration", "Window fit", "Text"],
                        datatype=["str", "str", "str", "str", "str"],
                        value=[],
                        interactive=False,
                        wrap=True,
                        label="Generated voice timeline",
                    )

            with gr.Tab("Settings"):
                with gr.Tabs():
                    with gr.Tab("Updates"):
                        update_status = gr.Markdown(
                            "```text\n[updates] Compare the running app, local checkout and official GitHub main\n[repair] Repair can restore modified tracked program files after saving a patch backup\n```",
                            elem_classes=["console"],
                        )
                        repair_confirm = gr.Checkbox(
                            label=(
                                "Allow Repair installation to replace modified tracked DubLocal program files "
                                "(a patch backup is saved first)"
                            ),
                            value=False,
                        )
                        with gr.Row():
                            check_update_button = gr.Button("Check for updates", variant="secondary")
                            install_update_button = gr.Button("Install update", variant="secondary")
                            repair_button = gr.Button("Repair installation", variant="secondary")
                            restart_button = gr.Button("Restart DubLocal", variant="primary")
                        gr.HTML(
                            """
                            <div class="dl-note">
                              Normal updates are clean fast-forwards only. Repair is explicit and preserves models,
                              shared caches, generated jobs and untracked user files.
                            </div>
                            """
                        )

                    with gr.Tab("Model Manager"):
                        gr.HTML(
                            """
                            <div class="dl-note" style="margin-bottom:12px">
                              Install optional AI resources here. DubLocal reuses compatible local engines and shared model
                              caches before downloading another copy.
                            </div>
                            """
                        )

                        with gr.Accordion("Whisper · transcription", open=True):
                            whisper_settings_status = gr.Markdown(
                                model_manager_status(), elem_classes=["console"]
                            )
                            whisper_model_settings = gr.Dropdown(
                                label="Whisper model",
                                choices=MODEL_CHOICES,
                                value="base",
                            )
                            with gr.Row():
                                install_whisper_button = gr.Button(
                                    "Install / verify model", variant="primary"
                                )
                                remove_whisper_button = gr.Button(
                                    "Remove model", variant="secondary"
                                )

                        with gr.Accordion("Contextual translation · Qwen3 4B", open=True):
                            contextual_settings_status = gr.Markdown(
                                contextual_translation_status("en", "ru", 0),
                                elem_classes=["console"],
                            )
                            with gr.Row():
                                prepare_contextual_button = gr.Button(
                                    "Prepare / verify contextual translation",
                                    variant="primary",
                                )
                                remove_contextual_button = gr.Button(
                                    "Remove DubLocal contextual model",
                                    variant="secondary",
                                )
                            gr.HTML(
                                """
                                <div class="dl-note">
                                  Recommended quality path. Uses the official Apache-2.0 Qwen3 4B Q4_K_M model (~2.5 GB)
                                  through MIT-licensed llama.cpp. DubLocal reuses llama.cpp if already installed and stores the
                                  model in the shared Hugging Face cache. No cloud translation fallback is used.
                                </div>
                                """
                            )

                        with gr.Accordion("Fast legacy translation · OPUS", open=False):
                            translation_route = gr.Dropdown(
                                label="Legacy translation model set",
                                choices=TRANSLATION_ROUTE_CHOICES,
                                value="en-to-many",
                            )
                            translation_settings_status = gr.Markdown(
                                _translation_route_status("en-to-many"),
                                elem_classes=["console"],
                            )
                            with gr.Row():
                                install_translation_button = gr.Button(
                                    "Install / verify legacy model(s)", variant="secondary"
                                )
                                remove_translation_button = gr.Button(
                                    "Remove DubLocal legacy translation models", variant="secondary"
                                )
                            gr.HTML(
                                """
                                <div class="dl-note">
                                  The OPUS path is kept for low-storage/fast use. It is sentence-level and is no longer the
                                  recommended default because it cannot provide the same dialogue context or translation quality.
                                </div>
                                """
                            )

                        with gr.Accordion("Kokoro · voice generation", open=True):
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
                            gr.HTML(
                                """
                                <div class="dl-note">
                                  DubLocal first looks for a compatible existing Kokoro environment. If found, it runs Kokoro
                                  there through an isolated worker and does not install a duplicate Python stack. Official
                                  model/voice assets use the shared Hugging Face cache.
                                </div>
                                """
                            )

                        model_action = gr.Markdown(
                            "```text\n[model manager] choose a model action above\n```",
                            elem_classes=["console"],
                        )

                    with gr.Tab("Local Resources"):
                        resource_status = gr.Markdown(
                            local_resource_status(), elem_classes=["console"]
                        )
                        refresh_resources_button = gr.Button(
                            "Rescan local resources", variant="secondary"
                        )
                        gr.HTML(
                            """
                            <div class="dl-note">
                              This view reports reusable system tools, shared caches and compatible external Python runtimes.
                              DubLocal never injects another application's site-packages into its own interpreter.
                            </div>
                            """
                        )

        gr.HTML(
            """
            <div class="dl-note">
              Current development version: 0.4.1.dev0 / M4 + M3.1. Context-aware local translation is now the default;
              duration fitting, original-audio ducking and stream-copy media export follow in M5.
            </div>
            """
        )

        source_type.change(
            fn=_toggle_source,
            inputs=[source_type],
            outputs=[youtube_url, local_file],
            queue=False,
        )
        scan_event = scan_button.click(
            fn=scan_source,
            inputs=[source_type, youtube_url, local_file],
            outputs=[status, subtitle_track, source_state, subtitle_preview],
        )
        scan_event.then(
            fn=_translation_status_for_ui,
            inputs=[
                translation_mode,
                translation_source_language,
                translation_target_language,
                source_state,
            ],
            outputs=[translation_status_main],
            queue=False,
        )
        extract_button.click(
            fn=extract_selected,
            inputs=[source_state, subtitle_track, rights],
            outputs=[
                subtitle_output,
                subtitle_preview,
                status,
                subtitle_path_state,
                translation_source_language,
            ],
        )
        transcribe_button.click(
            fn=transcribe_selected,
            inputs=[source_state, rights, whisper_model_main, source_language],
            outputs=[
                subtitle_output,
                subtitle_preview,
                status,
                subtitle_path_state,
                translation_source_language,
            ],
        )

        for component in (
            translation_mode,
            translation_source_language,
            translation_target_language,
        ):
            component.change(
                fn=_translation_status_for_ui,
                inputs=[
                    translation_mode,
                    translation_source_language,
                    translation_target_language,
                    source_state,
                ],
                outputs=[translation_status_main],
                queue=False,
            )

        translate_button.click(
            fn=_translate_with_state,
            inputs=[
                translation_mode,
                subtitle_path_state,
                translation_source_language,
                translation_target_language,
            ],
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
        tts_language.change(
            fn=_voice_dropdown,
            inputs=[tts_language],
            outputs=[tts_voice],
            queue=False,
        )
        generate_voice_button.click(
            fn=_generate_voice_ui,
            inputs=[
                voice_source,
                subtitle_path_state,
                translated_path_state,
                tts_language,
                tts_voice,
                tts_speed,
            ],
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
            outputs=[whisper_settings_status, model_status_main, model_action],
        )
        remove_whisper_button.click(
            fn=_remove_whisper_settings,
            inputs=[whisper_model_settings],
            outputs=[whisper_settings_status, model_status_main, model_action],
        )

        prepare_contextual_button.click(
            fn=_prepare_contextual_settings,
            inputs=[
                translation_mode,
                translation_source_language,
                translation_target_language,
                source_state,
            ],
            outputs=[
                contextual_settings_status,
                translation_status_main,
                resource_status,
                model_action,
            ],
        )
        remove_contextual_button.click(
            fn=_remove_contextual_settings,
            inputs=[
                translation_mode,
                translation_source_language,
                translation_target_language,
                source_state,
            ],
            outputs=[
                contextual_settings_status,
                translation_status_main,
                resource_status,
                model_action,
            ],
        )

        translation_route.change(
            fn=_translation_route_status,
            inputs=[translation_route],
            outputs=[translation_settings_status],
            queue=False,
        )
        install_translation_button.click(
            fn=_prepare_translation_settings,
            inputs=[
                translation_route,
                translation_mode,
                translation_source_language,
                translation_target_language,
                source_state,
            ],
            outputs=[translation_settings_status, translation_status_main, model_action],
        )
        remove_translation_button.click(
            fn=_remove_translation_settings,
            inputs=[
                translation_route,
                translation_mode,
                translation_source_language,
                translation_target_language,
                source_state,
            ],
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

        refresh_resources_button.click(
            fn=refresh_resources_ui,
            outputs=[resource_status],
        )
        check_update_button.click(
            fn=check_updates_ui,
            outputs=[update_status],
        )
        install_update_button.click(
            fn=install_update_ui,
            outputs=[update_status],
        )
        repair_button.click(
            fn=repair_installation_ui,
            inputs=[repair_confirm],
            outputs=[update_status],
        )
        restart_button.click(
            fn=restart_ui,
            outputs=[update_status],
        )

    return demo
