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


# Final product-level theme override. Keep this in the outermost UI layer so the
# established Main/Settings behaviour remains untouched while Gradio's own neutral
# and loader defaults inherit DubLocal's dark-green visual language consistently.
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
  --link-text-color-hover: var(--dl-green) !important;
  --link-text-color-hover-dark: var(--dl-green) !important;
  --code-background-fill: #07100a !important;
  --code-background-fill-dark: #07100a !important;
}

/* Gradio's request progress uses --loader-color, but keep explicit selectors as a
   compatibility guard across supported Gradio 5/6 frontend revisions. */
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

MATRIX_CSS = previous.MATRIX_CSS + THEME_CONSISTENCY_CSS


def build_app() -> gr.Blocks:
    return previous.build_app()
