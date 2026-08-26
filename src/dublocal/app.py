from __future__ import annotations

from html import escape
from typing import Any

import gradio as gr

from .media import DubLocalError, extract_subtitle, inspect_local_media, inspect_youtube


MATRIX_CSS = r"""
:root {
  --dl-bg: #07100a;
  --dl-panel: #0b1510;
  --dl-panel-2: #101b15;
  --dl-border: #1d5a35;
  --dl-green: #42ef83;
  --dl-green-soft: #89f5ad;
  --dl-text: #e6eee9;
  --dl-muted: #94a79b;
  --dl-danger: #ff7b72;
}

html, body, .gradio-container {
  background: radial-gradient(circle at top, #0c1710 0%, var(--dl-bg) 42%, #050806 100%) !important;
  color: var(--dl-text) !important;
}

.gradio-container {
  max-width: 1040px !important;
  margin: 0 auto !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

.dl-header {
  padding: 24px 4px 10px 4px;
}

.dl-brand {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -1px;
  color: var(--dl-green);
  text-shadow: 0 0 22px rgba(66, 239, 131, 0.13);
}

.dl-cursor {
  animation: dl-blink 1.15s steps(1, end) infinite;
}

@keyframes dl-blink {
  0%, 52% { opacity: 1; }
  53%, 100% { opacity: 0.18; }
}

.dl-subtitle {
  margin-top: 5px;
  color: var(--dl-muted);
  font-size: 14px;
}

.dl-local {
  display: inline-block;
  margin-left: 10px;
  padding: 3px 8px;
  border: 1px solid var(--dl-border);
  border-radius: 999px;
  color: var(--dl-green-soft);
  font: 600 11px ui-monospace, SFMono-Regular, Menlo, monospace;
  vertical-align: middle;
}

.gr-panel, .block, .form, .wrap {
  border-color: rgba(43, 108, 66, 0.55) !important;
}

button.primary {
  background: var(--dl-green) !important;
  color: #041008 !important;
  border: 1px solid var(--dl-green) !important;
  font-weight: 700 !important;
}

button.secondary {
  background: var(--dl-panel-2) !important;
  color: var(--dl-green-soft) !important;
  border: 1px solid var(--dl-border) !important;
}

.console {
  background: #050a07 !important;
  border: 1px solid var(--dl-border) !important;
  border-radius: 10px !important;
  padding: 14px 16px !important;
  min-height: 108px;
}

.console, .console * {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
  font-size: 13px !important;
}

.dl-note {
  color: var(--dl-muted);
  font-size: 12px;
}
"""


def _duration_label(seconds: float | None) -> str:
    if seconds is None:
        return "unknown duration"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _size_label(size: int | None) -> str:
    if not size:
        return "unknown size"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if value < 1024 or candidate == units[-1]:
            break
        value /= 1024
    return f"{value:.1f} {unit}"


def _summary(info: dict[str, Any]) -> str:
    tracks = info.get("subtitle_tracks", [])
    if info.get("kind") == "local":
        video_count = sum(1 for s in info.get("streams", []) if s.get("codec_type") == "video")
        audio_count = sum(1 for s in info.get("streams", []) if s.get("codec_type") == "audio")
        lines = [
            "[scan] local source ready",
            f"[file] {info.get('title', 'unknown')}",
            f"[media] {_duration_label(info.get('duration'))} · {_size_label(info.get('size'))}",
            f"[streams] {video_count} video · {audio_count} audio · {len(tracks)} subtitle",
        ]
    else:
        lines = [
            "[scan] YouTube source ready",
            f"[video] {info.get('title', 'Untitled')}",
            f"[channel] {info.get('uploader') or 'unknown'}",
            f"[media] {_duration_label(info.get('duration'))}",
            f"[captions] {len(tracks)} available track(s)",
        ]

    if tracks:
        lines.append("[next] choose a subtitle track and extract")
    else:
        lines.append("[next] no captions found — local transcription fallback is M2")
    return "```text\n" + "\n".join(lines) + "\n```"


def _error_status(message: str) -> str:
    return f"```text\n[error] {message}\n```"


def _toggle_source(source_type: str):
    youtube = source_type == "YouTube"
    return gr.Textbox(visible=youtube), gr.File(visible=not youtube)


def scan_source(source_type: str, youtube_url: str, local_file: str | None):
    try:
        if source_type == "YouTube":
            info = inspect_youtube(youtube_url)
        else:
            if not local_file:
                raise DubLocalError("Choose a local media file first.")
            info = inspect_local_media(local_file)

        tracks = info.get("subtitle_tracks", [])
        choices = [(item["label"], item["value"]) for item in tracks]
        value = choices[0][1] if choices else None
        selector = gr.Dropdown(
            choices=choices,
            value=value,
            interactive=bool(choices),
        )
        return _summary(info), selector, info
    except Exception as exc:  # UI boundary: convert backend errors to a readable status.
        message = str(exc) if isinstance(exc, DubLocalError) else f"Unexpected error: {exc}"
        return _error_status(message), gr.Dropdown(choices=[], value=None, interactive=False), {}


def extract_selected(info: dict[str, Any], track_value: str | None, rights_confirmed: bool):
    if not rights_confirmed:
        return None, _error_status("Confirm that you have the right or legal authority to process this media.")
    if not info:
        return None, _error_status("Scan a source first.")
    if not track_value:
        return None, _error_status(
            "No extractable subtitle track is selected. M2 will add local transcription when captions are absent."
        )

    try:
        output = extract_subtitle(info, track_value)
        return str(output), (
            "```text\n"
            "[done] subtitle extraction complete\n"
            f"[output] {output.name}\n"
            "[next] translation and transcription are intentionally not faked in M1\n"
            "```"
        )
    except Exception as exc:
        message = str(exc) if isinstance(exc, DubLocalError) else f"Unexpected error: {exc}"
        return None, _error_status(message)


def build_app() -> gr.Blocks:
    with gr.Blocks(css=MATRIX_CSS, title="DubLocal_") as demo:
        gr.HTML(
            """
            <div class="dl-header">
              <div class="dl-brand">DubLocal<span class="dl-cursor">_</span><span class="dl-local">LOCAL</span></div>
              <div class="dl-subtitle">Subtitles, translation and voice-over dubbing — processed on your Mac.</div>
            </div>
            """
        )

        source_state = gr.State({})

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
                label="Subtitle / caption track",
                choices=[],
                interactive=False,
            )
            rights = gr.Checkbox(
                label="I have the right or legal authority to process this media",
                value=False,
            )
            extract_button = gr.Button("Extract subtitles", variant="secondary")

        status = gr.Markdown(
            "```text\n[ready] choose a source and scan it\n[mode] M1 · existing subtitle acquisition\n```",
            elem_classes=["console"],
        )
        subtitle_output = gr.File(label="Subtitle output", interactive=False)

        gr.HTML(
            """
            <div class="dl-note">
              M1 deliberately stops at reliable caption discovery/extraction. The next milestone adds local transcription
              when captions are missing, followed by translation, Kokoro TTS, timing and audio mixing.
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
            outputs=[status, subtitle_track, source_state],
        )
        extract_button.click(
            fn=extract_selected,
            inputs=[source_state, subtitle_track, rights],
            outputs=[subtitle_output, status],
        )

    return demo


def main() -> None:
    demo = build_app()
    demo.queue(default_concurrency_limit=1).launch(
        inbrowser=True,
        server_name="127.0.0.1",
        show_error=False,
    )


if __name__ == "__main__":
    main()
