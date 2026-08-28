from __future__ import annotations

from typing import Any

import gradio as gr

from . import magic_flow
from . import ui_v050 as detailed
from . import ui_v060_refined as previous
from .adaptive_audio import (
    MIX_STRATEGY_CHOICES,
    advanced_mix_preference,
    audio_mix_status,
    last_mix_summary,
    prepare_separation_ui,
    render_magic_dubbed_media,
    set_advanced_mix_preference,
)


MATRIX_CSS = previous.MATRIX_CSS

# Magic Flow is intentionally always automatic. Advanced can override its own export
# strategy without changing the one-click Simple contract.
magic_flow.render_dubbed_media = render_magic_dubbed_media


class _InjectedTabContext:
    """Add v0.6.1 audio controls around existing tabs without rebuilding their content."""

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

        if self._label == "Advanced":
            self._original_html(
                '<div class="dl-compact-note"><strong>Audio mix</strong> · Auto keeps the fast dialogue path for normal material and uses prepared vocal separation only when music is strongly indicated.</div>'
            )
            strategy = gr.Dropdown(
                label="Audio mix strategy",
                choices=MIX_STRATEGY_CHOICES,
                value=advanced_mix_preference(),
                interactive=True,
            )
            status = gr.Markdown(
                audio_mix_status(),
                elem_classes=["console"],
            )
            strategy.change(
                fn=set_advanced_mix_preference,
                inputs=[strategy],
                outputs=[status],
                queue=False,
            )

        elif self._label == "Settings":
            with gr.Accordion("Vocal separation · music-aware dubbing", open=False):
                status = gr.Markdown(audio_mix_status(), elem_classes=["console"])
                prepare = gr.Button("Prepare vocal separation", variant="secondary")
                self._original_html(
                    '<div class="dl-note">Optional Demucs vocal separation runs locally in an isolated runtime. The compatibility baseline is CPU inference with chunk size selected from available memory, so the same feature can run on 8 GB M1-class Macs and larger M-series machines. Simple mode never requires this model to finish a dub.</div>'
                )
                prepare.click(
                    fn=prepare_separation_ui,
                    outputs=[status],
                )

        return result

    def __exit__(self, exc_type, exc, tb):
        if self._context is None:
            return False
        return self._context.__exit__(exc_type, exc, tb)


def _render_with_mix_summary(*args, **kwargs):
    result = _ORIGINAL_RENDER_UI(*args, **kwargs)
    if not isinstance(result, tuple) or len(result) != 2:
        return result
    output, card = result
    card_text = str(card).replace(
        "strong source-dialogue suppression",
        last_mix_summary(),
    )
    return output, card_text


_ORIGINAL_RENDER_UI = detailed._render_m5_ui


def build_app() -> gr.Blocks:
    """Layer audio architecture controls onto the stable Simple/Advanced v0.6 UI."""

    original_tab = gr.Tab
    original_html = gr.HTML
    original_render = detailed._render_m5_ui

    def tab_wrapper(*args: Any, **kwargs: Any):
        label = args[0] if args else kwargs.get("label")
        if label in {"Advanced", "Settings"}:
            return _InjectedTabContext(original_tab, original_html, args, kwargs)
        return original_tab(*args, **kwargs)

    # ui_v060 temporarily wraps the same Gradio Tab symbol for Main/Simple/Advanced.
    # Supplying this wrapper as its original Tab lets both layers compose rather than
    # replacing the stable builder.
    gr.Tab = tab_wrapper
    detailed._render_m5_ui = _render_with_mix_summary
    try:
        return previous.build_app()
    finally:
        gr.Tab = original_tab
        detailed._render_m5_ui = original_render
