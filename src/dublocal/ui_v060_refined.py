from __future__ import annotations

import gradio as gr

from . import ui_v060 as previous


# Keep the four-choice Magic Flow intact. The media choice already supports a
# subtitles-only package when Translate and Voice-over are off; make that capability
# discoverable without adding another button or accordion to the compact UI.
previous.MAGIC_TASK_CHOICES = [
    ("Subtitles", "subtitles"),
    ("Translate", "translate"),
    ("Voice-over", "voice"),
    ("Media file · original + subtitles if Translate/Voice are off", "media"),
]

MATRIX_CSS = previous.MATRIX_CSS


def build_app() -> gr.Blocks:
    return previous.build_app()
