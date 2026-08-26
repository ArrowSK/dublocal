from __future__ import annotations

import gradio as gr

from .app import (
    LANGUAGE_CHOICES,
    MATRIX_CSS,
    MODEL_CHOICES,
    TARGET_LANGUAGE_CHOICES,
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
    translation_status_ui,
)
from .dependencies import local_resource_status
from .transcription import model_manager_status
from .translation import translation_manager_status


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


def _install_whisper_settings(model_id: str):
    status, action = install_selected_model(model_id)
    return status, status, action


def _remove_whisper_settings(model_id: str):
    status, action = remove_selected_model(model_id)
    return status, status, action


def _prepare_translation_settings(
    route: str,
    main_source_language: str,
    main_target_language: str,
):
    source, target = _translation_route_languages(route)
    settings_status, action = prepare_translation_ui(source, target)
    main_status = translation_status_ui(main_source_language, main_target_language)
    return settings_status, main_status, action


def _remove_translation_settings(
    route: str,
    main_source_language: str,
    main_target_language: str,
):
    source, target = _translation_route_languages(route)
    settings_status, action = remove_translation_models_ui(source, target)
    main_status = translation_status_ui(main_source_language, main_target_language)
    return settings_status, main_status, action


def build_app() -> gr.Blocks:
    with gr.Blocks(title="DubLocal_") as demo:
        gr.HTML(
            """
            <div class="dl-header">
              <div class="dl-brand">DubLocal<span class="dl-cursor">_</span><span class="dl-local">LOCAL</span></div>
              <div class="dl-subtitle">Subtitles, translation and voice-over dubbing — processed on your Mac.</div>
            </div>
            """
        )

        source_state = gr.State({})
        subtitle_path_state = gr.State("")

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
                          Whisper model installation and removal now live in <strong>Settings → Model Manager</strong>.
                          The Main tab is for processing media, not maintaining the application.
                        </div>
                        """
                    )

                status = gr.Markdown(
                    "```text\n[ready] choose a source and scan it\n[mode] M3 · captions + local transcription + local translation\n```",
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
                        translation_manager_status("auto", "en"),
                        elem_classes=["console"],
                    )
                    translate_button = gr.Button("Translate subtitles", variant="primary")
                    gr.HTML(
                        """
                        <div class="dl-note">
                          Translation runs locally. Install or verify translation models in
                          <strong>Settings → Model Manager</strong>. Main keeps only the controls needed for the current job.
                        </div>
                        """
                    )
                    translated_output = gr.File(label="Translated SRT", interactive=False)
                    translated_preview = gr.Dataframe(
                        headers=["Start", "End", "Original", "Translation"],
                        datatype=["str", "str", "str", "str"],
                        value=[],
                        interactive=False,
                        wrap=True,
                        label="Translated subtitle preview",
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
                              Install optional AI models here. Processing controls stay on Main. DubLocal reuses compatible
                              local engines and shared model caches before downloading another copy.
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

                        with gr.Accordion("OPUS · subtitle translation", open=True):
                            translation_route = gr.Dropdown(
                                label="Translation model set",
                                choices=TRANSLATION_ROUTE_CHOICES,
                                value="en-to-many",
                            )
                            translation_settings_status = gr.Markdown(
                                _translation_route_status("en-to-many"),
                                elem_classes=["console"],
                            )
                            with gr.Row():
                                install_translation_button = gr.Button(
                                    "Install / verify required model(s)", variant="primary"
                                )
                                remove_translation_button = gr.Button(
                                    "Remove DubLocal translation models", variant="secondary"
                                )
                            gr.HTML(
                                """
                                <div class="dl-note">
                                  English → another supported language needs the ~310 MiB English-to-many model.
                                  Another supported language → English needs the ~310 MiB many-to-English model.
                                  Translation between two non-English languages uses both through English as a local pivot.
                                  Exact pinned snapshots are stored/reused through the normal Hugging Face cache.
                                </div>
                                """
                            )

                        with gr.Accordion("Kokoro · voice generation", open=False):
                            gr.Markdown(
                                "M4 will add Kokoro controls here. Existing compatible Kokoro installations are detected "
                                "under **Local Resources** and will be reused through an isolated worker instead of mixing "
                                "virtual environments."
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
              Current development version: 0.3.x / M3. Kokoro voice generation is M4; audio mixing and stream-copy media
              export follow in M5/M6.
            </div>
            """
        )

        source_type.change(
            fn=_toggle_source,
            inputs=[source_type],
            outputs=[youtube_url, local_file],
            queue=False,
        )
        scan_button.click(
            fn=scan_source,
            inputs=[source_type, youtube_url, local_file],
            outputs=[status, subtitle_track, source_state, subtitle_preview],
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
        translation_source_language.change(
            fn=translation_status_ui,
            inputs=[translation_source_language, translation_target_language],
            outputs=[translation_status_main],
            queue=False,
        )
        translation_target_language.change(
            fn=translation_status_ui,
            inputs=[translation_source_language, translation_target_language],
            outputs=[translation_status_main],
            queue=False,
        )
        translate_button.click(
            fn=translate_selected,
            inputs=[subtitle_path_state, translation_source_language, translation_target_language],
            outputs=[translated_output, translated_preview, status],
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

        translation_route.change(
            fn=_translation_route_status,
            inputs=[translation_route],
            outputs=[translation_settings_status],
            queue=False,
        )
        install_translation_button.click(
            fn=_prepare_translation_settings,
            inputs=[translation_route, translation_source_language, translation_target_language],
            outputs=[translation_settings_status, translation_status_main, model_action],
        )
        remove_translation_button.click(
            fn=_remove_translation_settings,
            inputs=[translation_route, translation_source_language, translation_target_language],
            outputs=[translation_settings_status, translation_status_main, model_action],
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
