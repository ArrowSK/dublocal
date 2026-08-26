# DubLocal_

Local-first macOS app for subtitle generation, translation, and AI voice-over dubbing from YouTube and local media.

> Status: early development. Milestone 1 already provides source inspection, subtitle discovery/extraction, and a simple Matrix-inspired Gradio UI. Translation, transcription fallback, dubbing, and packaging come next.

## Principles

- Local-first: media processing stays on the user's Mac by default.
- Simple UX: choose source, choose target language, choose output, process.
- Modular backends: transcription, translation, TTS, and rendering are replaceable components.
- Licence-aware: bundled models and binaries require explicit licence metadata.
- No DRM or access-control circumvention.

## Current milestone

Implemented now:

- YouTube URL scanning through the Python `yt-dlp` package;
- creator/automatic caption discovery;
- caption extraction without downloading the YouTube video or audio;
- local AVI/MKV/MP4/M4A-style media inspection through `ffprobe`;
- embedded text-subtitle discovery and extraction through `ffmpeg`;
- clear handling of image-based subtitle streams rather than silently pretending OCR worked;
- rights-confirmation gate before extraction;
- Matrix-inspired, restrained dark/green Gradio interface;
- automated tests for the media foundation.

## Quick start for development

Requirements:

- macOS;
- Python 3.11+;
- FFmpeg/ffprobe available on `PATH`.

With Homebrew:

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
dublocal
```

DubLocal opens locally in your default browser and binds to `127.0.0.1`; it is not exposed to your LAN by default.

A future release will remove the Homebrew/Python setup from the normal-user workflow and ship as a proper macOS application.

## Planned workflow

```text
YouTube URL / local media
        ↓
subtitle discovery
        ↓
existing captions OR local transcription
        ↓
optional translation
        ↓
optional TTS voice-over
        ↓
timing + audio ducking
        ↓
preview / SRT / VTT / audio / video export
```

## Development roadmap

1. ✅ Gradio shell and Matrix-inspired theme
2. ✅ Local media inspection with ffprobe
3. ✅ YouTube metadata and subtitle discovery with yt-dlp
4. ◐ Subtitle extraction and normalized internal timeline
5. ☐ Local transcription backend
6. ☐ Translation backend + licence-aware model manager
7. ☐ Kokoro TTS backend
8. ☐ Timing and audio ducking
9. ☐ Rendered preview/export
10. ☐ macOS packaging and release automation

Architecture details are in `docs/ARCHITECTURE.md`.

## Legal notice

DubLocal is a media-processing tool. Process only media you have the right or legal authority to download, translate, modify, or redistribute. The project does not grant rights to third-party content and does not include DRM or access-control circumvention.

## Licence

Apache-2.0. Third-party components and model weights retain their own licences; see `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json` as the project develops.
