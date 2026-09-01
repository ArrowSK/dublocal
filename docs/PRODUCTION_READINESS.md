# DubLocal 1.0 production readiness

This is a release-readiness audit rather than a feature wishlist. Beta 8 closes the main runtime-composition debt that previously made 1.0 hard to reason about; remaining work is mostly distribution, reproducibility, diagnostics and real-device acceptance testing.

## Current status

Current packaged beta: **0.6.0b8**.

The active application now has one explicit launcher/UI composition and canonical Standard/Advanced processing services. Package import is side-effect free, the active production path does not replace imported functions/classes or Gradio constructors at runtime, and architecture tests guard that rule.

The macOS CI workflow builds a real unsigned DMG on a macOS runner. Normal CI covers Python 3.11/3.13 and includes the Windows portability contract used by the Hungarian provider. This is meaningful beta validation, but it is not yet the signed/notarized, self-contained, immutable release distribution expected for 1.0.

## P0 — required before calling the app 1.0

### 1. Complete compatibility-module retirement deliberately

The active production path is consolidated. Historical compatibility/refinement modules may still exist in the repository for regression context or old direct callers, but they are not imported by the production composition root.

Before 1.0:

- remove dormant compatibility modules incrementally when no tests/documentation/direct development entry point still requires them;
- keep the production architecture guardrails so runtime monkeypatch composition cannot return accidentally;
- treat each deletion as maintenance with regression coverage, not as an excuse to redesign the working pipeline.

This is no longer a blocker to the beta runtime itself; it is repository hygiene before the codebase is declared stable.

### 2. Ship a signed/notarized production macOS artifact

The beta already builds a conventional drag-to-Applications DMG and verifies the generated application is intentionally unsigned. For 1.0 the distribution should add:

- Apple Developer ID signing;
- notarization;
- one authoritative semantic version/build number;
- release-artifact integrity verification;
- clean install/uninstall behavior;
- a packaging decision on whether Python remains a managed prerequisite or becomes part of a self-contained runtime.

Large optional models should remain outside the application bundle and continue using explicit model setup.

### 3. Move stable updates from mutable `main` to immutable releases

The current in-app updater deliberately manages the official `main` checkout with branch/upstream/divergence safeguards and repair backup behavior. That is suitable for the beta channel.

Before 1.0:

- make Stable follow immutable signed/tagged releases;
- optionally retain Beta as the current `main`/prerelease channel or another explicit prerelease channel;
- verify downloaded release assets before installation;
- retain rollback to the previous working release.

### 4. Add end-to-end macOS smoke/acceptance coverage

Current macOS CI verifies the actual DMG build, package contracts and shell/package mechanics. The remaining release gap is behavioral smoke testing on real production-like Macs.

Before 1.0, automate where practical and manually validate where hardware matters:

- application launch and localhost-only binding;
- FFmpeg/ffprobe discovery;
- a tiny deterministic local-file transcription fixture;
- Standard local-file end-to-end processing;
- MP4/MKV/Shareable export, including burned-subtitle capability selection;
- updater/restart behavior against a controlled release fixture;
- authenticated-source redaction/selection/DRM boundaries without storing reusable credentials;
- low-memory M1-class and newer higher-memory Apple Silicon acceptance runs.

GitHub-hosted runners cannot fully substitute for representative unified-memory Macs.

### 5. Make dependency resolution more reproducible

Core dependencies are constrained, and optional engines/models already use several pinned revisions/checksums, but 1.0 should reduce exposure to upstream drift further.

Before 1.0:

- maintain tested production constraints/lock data for the application runtime;
- record tested/minimum versions of FFmpeg, whisper.cpp, llama.cpp and optional audio/TTS runtimes;
- preserve model revision/checksum verification;
- ensure a release build can be reproduced from declared inputs without relying on an unrecorded local environment.

### 6. Synchronize legal inventory with the release build

The project already separates application licensing from third-party/model licensing and keeps GPL Piper out of the Apache-2.0 process via an isolated runtime.

Before 1.0:

- generate/reconcile third-party and model notices against the exact release configuration;
- re-check redistribution/commercial-use statements for every bundled or automatically prepared component;
- keep OS-provided system voices explicitly outside DubLocal redistribution claims.

## P1 — strongly recommended for 1.0

- A single **System Check / Diagnostics** screen that can export a privacy-safe support bundle with versions, executables, model readiness and recent logs.
- Versioned user-config migrations for settings/model/provider receipts.
- A clear Stable/Beta update-channel selector once immutable stable releases exist.
- Release-candidate acceptance fixtures for dialogue-heavy, music-heavy, local-file and representative online-source jobs.
- More explicit performance/ETA telemetry for long model stages without compromising local privacy.

## What does not need rewriting

The current product shape can stay:

- Standard as the default consumer workflow;
- Advanced for stage-by-stage control;
- one sequential queue;
- explicit optional model downloads;
- hardware-aware translation recommendations;
- local-first processing;
- provider-neutral source/TTS boundaries;
- format-aware output profiles;
- conservative subtitle/translation validation.

The 1.0 effort should therefore be treated as **distribution and release hardening**, not another pipeline rewrite.

## Recommended sequence

1. Keep the beta 8 explicit production composition stable while deleting dormant compatibility files incrementally.
2. Add production constraints and behavioral macOS smoke fixtures.
3. Decide/package the signed/notarized 1.0 runtime shape.
4. Move Stable updates to immutable verified releases while keeping Beta explicit.
5. Reconcile legal/notices and run the representative-Mac acceptance matrix.
6. Tag a release candidate, validate the exact artifact, then promote that tested artifact to 1.0.
