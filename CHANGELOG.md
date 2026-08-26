# DubLocal changelog

DubLocal is still in active development. The versions below describe development builds from the `main` branch.

> **Current development build:** `v0.3.0.dev0` — **M3 Local Translation**
>
> A packaged GitHub Release has **not** been published yet. The first public packaged release will be created only after the corresponding build has been validated and the macOS distribution work is ready.

## v0.3.0.dev0 — M3 Local Translation — current

M3 turns the timestamped subtitle timeline from M2 into a fully local translation workflow.

### Added

- Local subtitle translation with pinned Apache-2.0 Helsinki-NLP OPUS models.
- English ↔ supported-language translation with one model, and non-English ↔ non-English translation through a local English pivot.
- Original/translated side-by-side subtitle preview.
- Translated SRT export with the original timestamps preserved exactly.
- Whisper Auto-detected language handoff into the translation workflow.
- Shared Hugging Face cache reuse: an identical pinned model already downloaded by another compatible local app can be reused instead of stored a second time.
- Compatible external Python-runtime discovery. Heavy stacks already present in another known local environment can be reused through an isolated worker process rather than mixing virtual environments.
- Reusable-resource reporting for FFmpeg, ffprobe, whisper.cpp, Hugging Face cache and detected Kokoro runtime availability.
- **Repair installation** for Git-based development installs, modeled on NarRoam Studio's recovery behavior.
- New top-level **Main** and **Settings** navigation.
- **Settings → Updates**, **Settings → Model Manager**, and **Settings → Local Resources** subtabs.
- Whisper and OPUS installation/removal moved out of the processing flow into the dedicated Model Manager.
- Translation Model Manager presets for English → supported languages, supported languages → English, and non-English ↔ non-English routes.

### Update and repair changes

Normal in-app updates remain conservative: DubLocal accepts only the official `ArrowSK/dublocal` `main` branch, fast-forwards clean installations and refuses to overwrite tracked local edits.

If tracked DubLocal program files have been modified, **Repair installation** can now:

1. save the local Git diff as a patch under `~/.dublocal/repair-backups/`;
2. restore tracked program files from official GitHub `main`;
3. refresh the managed DubLocal Python core;
4. verify the imported version and module path;
5. restart DubLocal cleanly.

Repair does not delete optional models, shared caches, generated jobs or untracked user files, and it will not rewrite local commits or diverged Git history.

### Storage/reuse policy

DubLocal now prefers reuse over duplication where that is technically safe:

- system executables are reused in place;
- Hugging Face model snapshots use the normal shared Hugging Face cache;
- compatible external Python environments can be used through separate-process workers;
- packages from one virtual environment are never injected into another virtual environment's interpreter.

This same external-runtime mechanism is intended for M4 Kokoro integration.

### Planned output behavior recorded for M5

Dubbed-media export will avoid unnecessary video re-encoding. Compatible source video will be stream-copied while DubLocal creates/re-encodes only the new mixed audio track. The user will be able to choose between making the DubLocal mix the primary/default audio stream or adding it as a second selectable audio track while preserving the original audio.

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
