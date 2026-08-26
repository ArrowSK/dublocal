# DubLocal_

Local-first macOS app for subtitle generation, translation, and AI voice-over dubbing from YouTube and local media.

> Status: early development. The first milestone focuses on source inspection, subtitle discovery/extraction, and a simple Matrix-inspired Gradio UI.

## Principles

- Local-first: media processing stays on the user's Mac by default.
- Simple UX: choose source, choose target language, choose output, process.
- Modular backends: transcription, translation, TTS, and rendering are replaceable components.
- Licence-aware: bundled models and binaries require explicit licence metadata.
- No DRM or access-control circumvention.

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

1. Gradio shell and Matrix-inspired theme
2. Local media inspection with ffprobe
3. YouTube metadata and subtitle discovery with yt-dlp
4. Subtitle extraction and normalized internal timeline
5. Local transcription backend
6. Translation backend + licence-aware model manager
7. Kokoro TTS backend
8. Timing and audio ducking
9. Rendered preview/export
10. macOS packaging and release automation

## Legal notice

DubLocal is a media-processing tool. Process only media you have the right or legal authority to download, translate, modify, or redistribute. The project does not grant rights to third-party content and does not include DRM or access-control circumvention.

## Licence

Apache-2.0. Third-party components and model weights retain their own licences; see `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json` as the project develops.
