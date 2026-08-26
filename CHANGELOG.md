# DubLocal changelog

DubLocal is still in active development. The versions below describe development builds from the `main` branch.

> **Current development build:** `v0.4.0.dev0` — **M4 Local Voice**
>
> A packaged GitHub Release has **not** been published yet. The first public packaged release will be created only after the corresponding build has been validated and the macOS distribution work is ready.

## v0.4.0.dev0 — M4 Local Voice — current

M4 adds the first local speech-synthesis stage without changing the source movie soundtrack yet.

### Added

- Kokoro as the first local TTS backend.
- Reuse of a compatible existing Kokoro virtual environment through a separate worker process instead of copying that environment's packages into DubLocal.
- A fallback **Prepare Kokoro** action that installs DubLocal's optional Kokoro runtime only when no reusable runtime is available.
- Official Kokoro language and voice selectors.
- American and British English as separate pronunciation frontends/voice families.
- Voice-only WAV generation from either the source SRT or translated SRT.
- Per-subtitle segment WAV assets and a JSON generation manifest.
- Timeline assembly that keeps every subtitle start time and reports speech that overruns its current subtitle window.
- Model Manager controls for explicit Kokoro preparation/verification.
- Shared Hugging Face cache reuse for Kokoro model/voice assets.

### Runtime-discovery fix

M4 fixes an important macOS virtual-environment edge case. A venv's `bin/python` is often a symlink to the same framework Python used by other venvs. Earlier discovery resolved that symlink, which could make two different environments appear to be the same interpreter. DubLocal now preserves the venv entry-point path itself, so an environment such as `~/narroam-studio/.venv/bin/python` can be recognized as a distinct reusable runtime.

### Scope boundary

M4 does **not** replace dialogue in the original soundtrack and does not re-encode video. It produces a synchronized voice-only track. M5 adds duration fitting, original-audio ducking/mixing and the stream-copy/remux strategy for replacing the primary audio or adding a second selectable dubbed track.

Official Kokoro currently covers American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese. Translation targets such as Hungarian, Russian and German remain subtitle-only until another compatible local TTS backend is added.

## v0.3.0.dev0 — M3 Local Translation

M3 turned the timestamped subtitle timeline from M2 into a fully local translation workflow.

- Local subtitle translation with pinned Apache-2.0 Helsinki-NLP OPUS models.
- English ↔ supported-language translation with one model, and non-English ↔ non-English translation through a local English pivot.
- Original/translated side-by-side subtitle preview.
- Translated SRT export with the original timestamps preserved exactly.
- Whisper Auto-detected language handoff into the translation workflow.
- Shared Hugging Face cache reuse instead of unnecessary duplicate model copies.
- Compatible external Python-runtime discovery through isolated worker processes.
- Reusable-resource reporting for FFmpeg, ffprobe, whisper.cpp and the Hugging Face cache.
- **Repair installation** for Git-based development installs.
- Main/Settings navigation with Settings → Updates, Model Manager and Local Resources.
- Planned M5 behavior recorded: stream-copy compatible video and let the user replace the primary audio or add a second selectable dubbed track.

## v0.2.0.dev0 — M2 Local Transcription

- Added local `whisper.cpp` transcription.
- Added Tiny, Base and Small Whisper model management with checksum verification.
- Added source-language Auto/manual selection.
- Added timestamped SRT generation and preview.
- Added YouTube/local-file transcription fallback.
- Added the first in-app GitHub updater.
- Fixed Gradio output-path handling for generated subtitle files.
- M2 transcription was validated on an Apple Silicon Mac before Issue #1 was closed.

## v0.1.0.dev0 — M1 Source and Captions

- Added the Matrix-inspired Gradio shell.
- Added local media inspection with ffprobe.
- Added YouTube metadata/caption discovery with yt-dlp.
- Added existing subtitle/caption extraction.
- Added the branded macOS launcher and original DubLocal icon.
