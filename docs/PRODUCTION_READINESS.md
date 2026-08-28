# DubLocal 1.0 production readiness

This document is a release-readiness audit, not a feature wishlist. The current pipeline is already capable enough for a 1.0 candidate; the remaining work is mainly packaging, consolidation, reproducibility and real macOS validation.

## Current status

DubLocal is still explicitly a development build (`0.6.0.dev0`). The current install path is a Git checkout plus an editable Python environment and an AppleScript-generated launcher. Updates track mutable `main`. CI runs the Python unit suite on Ubuntu with Python 3.11 and 3.13.

Those choices are useful during rapid development but should not define the public 1.0 distribution.

## P0 — required before calling the app 1.0

### 1. Consolidate the layered implementation

The first UI cleanup pass is complete: the launcher now uses one active `product_ui.py` layer for the current Simple/Advanced shell, batch queue, update UX, model wizard, provider controls, audio controls and final theme. The superseded `ui_v060.py`, `ui_v060_refined.py`, `ui_v061.py`, `ui_v062.py`, `ui_v063.py` and `ui_v064.py` overlays have been removed after parity tests were added.

The remaining detailed-workflow builder still carries the older `ui_v053.py` → `ui_v050.py` → `ui_v042.py` → `ui.py` chain, and runtime refinements are still installed through several compatibility wrappers. Those layers protected working behavior while the product was changing quickly, but they should not remain the final 1.0 structure.

Before 1.0:

- consolidate the remaining detailed-workflow UI chain behind normal canonical modules;
- fold active transcription/TTS/audio refinements into their owning modules behind normal functions/classes rather than import-time monkeypatches;
- delete superseded compatibility modules only after regression tests prove parity;
- keep public behavior and the current Simple/Advanced UX unchanged during the cleanup.

The important rule is that this is consolidation, not a pipeline rewrite.

### 2. Ship a real macOS application artifact

The current installer creates launchers under `~/Applications` and keeps the Python virtual environment inside the Git checkout. The generated bundle also has its own hard-coded launcher version unrelated to the Python package version.

For 1.0, build a normal distributable macOS application (or a self-contained signed application plus DMG/ZIP) with:

- one authoritative semantic version;
- reproducible packaged runtime;
- Apple code signing and notarization;
- branded icon/metadata;
- clean install/uninstall behavior;
- no requirement for the user to clone a Git repository or run a shell script.

Large optional models should remain outside the application bundle and continue using DubLocal's explicit model setup flow.

### 3. Move stable updates from `main` to releases

The current one-button updater is good UX but it still updates from the official `main` branch. Production users should receive immutable releases rather than whatever happens to be at the tip of development.

Before 1.0:

- publish tagged GitHub Releases;
- make the default updater follow the stable release channel;
- optionally provide a separate Beta/Development channel;
- verify release asset checksum/signature before replacing the installed application;
- retain rollback to the previous working release.

### 4. Add macOS release CI and smoke tests

Current CI validates unit tests on Ubuntu/Python 3.11 and 3.13. That does not exercise the real production environment: macOS, Homebrew executables, VideoToolbox, app launch/restart or Apple Silicon-specific behavior.

The release pipeline should add macOS jobs that at minimum verify:

- application build/package;
- app starts and binds only to localhost;
- ffmpeg/ffprobe discovery;
- whisper.cpp discovery and a tiny deterministic transcription fixture;
- local-file Magic Flow smoke path;
- updater/relaunch logic against a controlled fixture;
- model setup state and migration behavior.

A small manual release matrix should still cover low-memory M1 and a newer high-memory M-series Mac because GitHub runners cannot represent every unified-memory profile.

### 5. Make dependency resolution reproducible

`pyproject.toml` currently uses broad dependency ranges and optional runtimes are partly installed through Homebrew or separate Python environments. That is appropriate for development but exposes production users to upstream breakage.

Before 1.0:

- maintain tested production constraints/lock data for the application runtime;
- pin or constrain known-sensitive packages such as Gradio, Kokoro/PyTorch and yt-dlp to tested ranges;
- record minimum/tested versions of ffmpeg, whisper.cpp, llama.cpp, eSpeak NG and Demucs runtime dependencies;
- keep model revision/checksum verification as it works today.

### 6. Synchronize documentation and legal notices with active code

Some top-level documentation still describes older behavior, including FFmpeg post-stretch timing and the pre-separation soundtrack model, while the active runtime now uses native Kokoro timing and optional vocal separation.

Before 1.0:

- make README, architecture, user guide and troubleshooting describe the same current behavior;
- generate the release's third-party/model licence notice from the actual enabled dependency/model registry;
- clearly distinguish official Kokoro models from third-party providers such as Russian Kokoro.

## P1 — strongly recommended for 1.0, but not architectural blockers

- A single **System Check / Diagnostics** screen that can export a privacy-safe support bundle containing versions, detected executables, model readiness and recent DubLocal logs.
- Versioned user-config migrations so future settings/model receipts can evolve without manual deletion.
- A clear Stable/Beta channel selector once release channels exist.
- Release-candidate acceptance tests for representative YouTube, local video, dialogue-heavy and music-heavy material.
- Graceful cancellation between long pipeline stages and queue items.

## What does not need rewriting

The core product architecture can stay: one sequential Magic Flow queue over the same transcription, translation, TTS, mixing and export engines; explicit optional model downloads; hardware-aware recommendations; local-only processing; and the Simple/Advanced split.

The 1.0 effort should therefore be treated as **productionization and consolidation**, not another feature milestone.

## Recommended sequence

1. Freeze new architecture-changing features.
2. Finish consolidating the remaining detailed UI/runtime overlays while preserving behavior.
3. Add macOS release/smoke CI and reproducible dependency constraints.
4. Build signed/notarized release artifacts and switch updater to tagged releases.
5. Synchronize docs/licences and run the release-candidate test matrix.
6. Tag `1.0.0-rc1`, test on representative M-series Macs, then promote the same tested artifact to `1.0.0`.
