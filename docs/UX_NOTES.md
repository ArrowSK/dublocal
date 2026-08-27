# DubLocal UX principles

This document captures the product-facing UX rules introduced in v0.4.2.dev0.

1. **Main is a workflow, not a control panel.** Show only the next useful stage by default. Detailed engine/model status belongs in Settings or collapsed diagnostics.
2. **Progressive disclosure.** Source comes first; subtitle tools appear after a source is scanned; translation/voice tools appear after a timed subtitle timeline exists.
3. **One visual language.** DubLocal uses green as its only accent. Browser/framework default orange accents are overridden.
4. **Visible version.** Settings always shows the running DubLocal version near the top.
5. **Long operations report progress.** Model downloads, contextual translation and local TTS expose percentage and estimated time remaining when measurable. Short/atomic operations show a stage progress indicator rather than a fake precision estimate.
6. **Advanced diagnostics are available but not dominant.** Engine paths, model hashes and raw status consoles stay accessible without occupying the main workflow by default.
7. **No feature loss for simplification.** Existing controls remain available; the default view is simply less busy.
