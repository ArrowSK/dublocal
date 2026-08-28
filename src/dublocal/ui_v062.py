from __future__ import annotations

from typing import Any

import gradio as gr

from . import ui_v061 as previous
from .tts_provider_refinement import (
    prepare_registered_provider_ui,
    register_custom_provider_ui,
    registered_provider_choices,
)
from .tts_provider_registry import provider_status_text


MATRIX_CSS = previous.MATRIX_CSS

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


def _register_and_refresh(manifest_text: str):
    status, action = register_custom_provider_ui(manifest_text)
    choices = registered_provider_choices()
    value = choices[-1][1] if choices else None
    return status, action, gr.Dropdown(choices=choices, value=value, interactive=bool(choices))


class _InjectedSettingsContext:
    """Add provider controls without rebuilding the stable v0.6.1 interface."""

    def __init__(self, original_tab, original_html, args, kwargs):
        self._original_tab = original_tab
        self._original_html = original_html
        self._args = args
        self._kwargs = kwargs
        self._context = None
        self._label = args[0] if args else kwargs.get("label")

    def __enter__(self):
        self._context = self._original_tab(*self._args, **self._kwargs)
        result = self._context.__enter__()
        if self._label == "Settings":
            with gr.Accordion("Local TTS providers · Russian & custom models", open=False):
                status = gr.Markdown(provider_status_text(), elem_classes=["console"])
                self._original_html(
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
                prepare.click(
                    fn=prepare_registered_provider_ui,
                    inputs=[provider],
                    outputs=[status, status],
                )

                self._original_html(
                    '<div class="dl-compact-note"><strong>Custom models are manifests, not plugins.</strong> DubLocal accepts only allowlisted local Kokoro-compatible frontends and model/voice/config files. Python modules, scripts, shell commands and arbitrary entrypoints are rejected. Remote manifests must pin an immutable commit revision; local mirrors are also supported.</div>'
                )
                manifest = gr.Code(
                    label="Custom provider manifest · JSON",
                    value=_EXAMPLE_MANIFEST,
                    language="json",
                    lines=18,
                )
                register = gr.Button("Validate & register custom provider", variant="secondary")
                action = gr.Markdown(
                    "```text\n[custom] edit the manifest, then validate/register it\n```",
                    elem_classes=["console"],
                )
                register.click(
                    fn=_register_and_refresh,
                    inputs=[manifest],
                    outputs=[status, action, provider],
                )
        return result

    def __exit__(self, exc_type, exc, tb):
        if self._context is None:
            return False
        return self._context.__exit__(exc_type, exc, tb)


def build_app() -> gr.Blocks:
    original_tab = gr.Tab
    original_html = gr.HTML

    def tab_wrapper(*args: Any, **kwargs: Any):
        label = args[0] if args else kwargs.get("label")
        if label == "Settings":
            return _InjectedSettingsContext(original_tab, original_html, args, kwargs)
        return original_tab(*args, **kwargs)

    gr.Tab = tab_wrapper
    try:
        return previous.build_app()
    finally:
        gr.Tab = original_tab
