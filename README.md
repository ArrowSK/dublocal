# DubLocal_

Local-first macOS app for subtitle generation, translation, and AI voice-over dubbing from YouTube and local media.

> Status: early development. Milestone 2 adds local whisper.cpp transcription with optional model management on top of the existing caption-discovery/extraction foundation and native macOS launcher.

## Principles

- Local-first: media processing stays on the user's Mac by default.
- Simple UX: choose source, use existing captions when available, or transcribe locally.
- Modular backends: transcription, translation, TTS, and rendering are replaceable components.
- Licence-aware: models and binaries require explicit licence metadata before distribution.
- Optional models: DubLocal core launches without downloading AI weights.
- No DRM or access-control circumvention.

## M2 implemented now

- YouTube URL scanning through the Python `yt-dlp` package;
- creator/automatic caption discovery;
- direct caption extraction with retry handling;
- controlled fallback when YouTube returns HTTP 429 for captions;
- local AVI/MKV/MP4/M4A-style media inspection through `ffprobe`;
- embedded text-subtitle extraction through `ffmpeg`;
- local speech transcription through `whisper.cpp` / `whisper-cli`;
- Apple Silicon Metal acceleration through whisper.cpp's normal macOS path;
- conservative CPU path on Intel Macs;
- local 16 kHz mono PCM preparation with FFmpeg;
- YouTube audio-only acquisition for user-authorized local transcription;
- source-language `Auto` plus manual language selection;
- normalized millisecond subtitle timeline and SRT output;
- timed subtitle preview in the UI;
- model manager for `tiny`, `base`, and `small` multilingual Whisper models;
- explicit install/remove actions — no model is silently downloaded;
- SHA-1 verification against upstream published model checksums before a model is used;
- rights-confirmation gate before extraction or transcription;
- native `DubLocal.app` launcher plus `Stop DubLocal.app`;
- original branded macOS icon;
- tests for media inspection, normalized timelines, and transcription orchestration.

## Install on macOS

Initial support target: macOS 13+ on Apple Silicon or Intel.

Clone once and run the installer:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates/refreshes the local `.venv`, checks FFmpeg, offers to install the small MIT-licensed `whisper.cpp` engine through Homebrew, generates the branded icon, and creates:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

Whisper model weights are deliberately **not** installed by the launcher installer. Open DubLocal and use **Local transcription → Install / verify model** when you actually want a model. `Base` (142 MiB) is the recommended starting point.

After installation, normal use is through `DubLocal.app`; Terminal is not required for launching the UI. The launcher uses `127.0.0.1:7861`, logs under `~/.dublocal/`, reuses an existing instance, and offers a clean restart after code updates.

Detailed installation and update instructions are in `docs/INSTALLATION.md`.

## Current workflow

```text
YouTube URL / local media
        ↓
source scan
        ↓
existing captions? ── yes ──→ extract
        │
        no / blocked
        ↓
local whisper.cpp transcription
        ↓
normalized timed SRT
        ↓
M3: translation
        ↓
M4+: TTS voice-over → timing → audio ducking → render/export
```

## Development roadmap

1. ✅ Gradio shell and Matrix-inspired theme
2. ✅ Local media inspection with ffprobe
3. ✅ YouTube metadata and subtitle discovery with yt-dlp
4. ✅ Subtitle extraction and normalized internal timeline
5. ✅ Local whisper.cpp transcription + model manager
6. ☐ Translation backend + licence-aware translation model manager
7. ☐ Kokoro TTS backend
8. ☐ Timing and audio ducking
9. ☐ Rendered preview/export
10. ◐ macOS packaging and release automation

Architecture details are in `docs/ARCHITECTURE.md`.

## Legal notice

DubLocal is a media-processing tool. Process only media you have the right or legal authority to download, translate, modify, or redistribute. The project does not grant rights to third-party content and does not include DRM or access-control circumvention.

## Licence

DubLocal is Apache-2.0. Third-party components and model weights retain their own licences; see `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json`.
