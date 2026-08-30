from __future__ import annotations

import gradio as gr

from .output_profiles import (
    DEFAULT_PROFILES,
    PROFILE_CHOICES,
    load_profiles,
    profile_summary,
    reset_profiles,
    save_profiles,
)


_INSTALLED = False


def _save(mkv: str, mp4: str, share: str):
    values = save_profiles(mkv, mp4, share)
    try:
        gr.Info("Output profiles saved.")
    except Exception:
        pass
    return profile_summary(values)


def _reset():
    values = reset_profiles()
    try:
        gr.Info("Output profiles restored to Auto.")
    except Exception:
        pass
    return (
        gr.Dropdown(value=values["mkv"]),
        gr.Dropdown(value=values["mp4"]),
        gr.Dropdown(value=values["share"]),
        profile_summary(values),
    )


def _build_output_profile_settings(original_html) -> None:
    values = load_profiles()
    with gr.Accordion("Output profiles", open=False):
        original_html(
            '<div class="dl-note"><strong>Auto is format-aware.</strong> MKV preserves source video whenever practical; regular MP4 targets a balanced compatible export; Shareable MP4 targets a compact file and avoids the old oversized 2.5–25 Mbps ladder. These are persistent defaults. The Standard workflow stays uncluttered; its Resolution limit remains an optional ceiling rather than a second compression system.</div>'
        )
        with gr.Row():
            mkv = gr.Dropdown(
                label="MKV",
                choices=PROFILE_CHOICES,
                value=values["mkv"],
                info="Auto preserves the source video unless you explicitly request a lower resolution.",
            )
            mp4 = gr.Dropdown(
                label="MP4",
                choices=PROFILE_CHOICES,
                value=values["mp4"],
                info="Auto uses Balanced: H.264-compatible, up to 1080p, and re-encodes only when the source is incompatible or materially larger than the target.",
            )
            share = gr.Dropdown(
                label="Shareable MP4",
                choices=PROFILE_CHOICES,
                value=values["share"],
                info="Auto uses Compact: up to 720p with a predictable sharing-oriented bitrate. Burned subtitles use the same profile.",
            )
        status = gr.Markdown(profile_summary(values), elem_classes=["console"])
        with gr.Row():
            save = gr.Button("Save output profiles", variant="primary")
            reset = gr.Button("Restore Auto defaults", variant="secondary")
        save.click(fn=_save, inputs=[mkv, mp4, share], outputs=[status], queue=False)
        reset.click(fn=_reset, outputs=[mkv, mp4, share, status], queue=False)


def install_output_profiles_ui(product_ui) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original = product_ui._build_settings_injections

    def build_settings(original_html) -> None:
        _build_output_profile_settings(original_html)
        original(original_html)

    product_ui._build_settings_injections = build_settings
