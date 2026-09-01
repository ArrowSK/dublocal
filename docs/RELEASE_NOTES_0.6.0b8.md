# DubLocal 0.6.0b8 — production architecture cleanup

Beta 8 is primarily a reliability and maintainability release. It keeps the existing user workflows and media behavior while replacing the accumulated import-time refinement stack with an explicit production composition.

## What changed

- The active application now has one explicit composition root in `launcher_runtime.py` and one production UI in `production_ui.py`.
- Standard, Advanced, batch, course, transcription, voice, audio and export work is connected through ordinary service calls rather than replacing module functions, classes or Gradio constructors at import time.
- Package import is side-effect free. Importing `dublocal` now exposes metadata only.
- The Standard workflow and Advanced workflow continue to use the same underlying processing services rather than separate implementations.
- Contextual Qwen translation keeps adaptive batching, source-language Auto detection, strict subtitle-ID validation, wrong-script rejection, protected caption tags, bounded recovery and local translation cache behavior.
- Whisper VAD fallback, anti-repetition protection and smart recovery are now invoked directly by the canonical transcription pipeline.
- Existing native voice timing, Hungarian routing, Russian/custom TTS providers, automatic vocal-range matching, adaptive audio mixing and format-aware output profiles remain available through explicit service boundaries.
- Authenticated course/website safety policy is now part of the canonical provider instead of a runtime patch. Signed HLS/DASH manifests are still inspected for encryption/DRM, reusable credential query values are redacted before persistence/UI errors, non-secret routing query parameters are preserved, and an explicit empty lesson selection stays empty.
- The Standard local-file selector now updates both its queue summary and the processing-button label correctly, fixing the callback output mismatch found during the architecture review.

## Architecture guardrails

The test suite now rejects the old production pattern where an imported module function/class or a Gradio constructor is replaced at runtime. Dormant historical compatibility modules are outside the active production composition and can be removed incrementally without changing the running application.

## Existing beta behavior retained

Beta 8 retains the major user-facing work from the previous betas, including Hungarian voice-over from beta 7, the contextual translation performance improvements from beta 6, format-aware output profiles from beta 5, and subtitle-capable FFmpeg handling for burned Shareable MP4 exports from beta 4.

## macOS package

The macOS beta remains intentionally unsigned and not notarized. Install it by dragging `DubLocal.app` to Applications, then Control-click/right-click and choose **Open** on first launch. If macOS still blocks it, use **System Settings → Privacy & Security → Open Anyway**. Do not disable Gatekeeper globally.

Large AI models are not bundled. Existing in-app update behavior remains the supported update path.
