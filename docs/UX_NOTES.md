# DubLocal UX principles

This document captures the product-facing UX rules for the packaged beta.

1. **Main has two clear modes.** `Standard` is the default and contains only the compact Standard workflow. `Advanced` contains the complete manual stage-by-stage workflow. They must never be rendered together as one long page.
2. **Standard is the normal product experience.** A typical user should be able to choose a source, target language and desired outputs, then start processing without understanding Whisper, Qwen, Kokoro, muxing or individual pipeline stages.
3. **Advanced is a workflow, not a control panel.** The manual path is `1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export`. Model/runtime detail belongs in Settings or collapsed diagnostics.
4. **Progressive disclosure.** A user can stop after subtitles, translation, voice generation or final export. Later stages must never be required to retrieve an earlier useful output.
5. **Packaging is independent from dubbing.** Export must support original media + source subtitles without requiring translation or TTS.
6. **Persistent stage state.** Source loading, transcription, translation, voice generation and export keep clear success/failure state on the same stage card. Toasts are supplemental.
7. **One visual language.** Green remains the product accent; framework defaults should not reintroduce unrelated orange states.
8. **Visible version.** Settings shows the actual running DubLocal version near the top.
9. **Long operations report meaningful progress.** Downloads, transcription, translation, TTS and render/remux expose percentage/ETA when the underlying operation permits it. Do not invent fake precision.
10. **Standard has one progress surface.** Processing progress appears in the persistent status area. Output-file components stay collapsed while processing so Gradio does not create several competing progress indicators for one job.
11. **Automatic choices must remain explainable.** Hardware-aware model recommendations, Auto source-language resolution, Auto voice matching and format-aware Auto output profiles simplify the normal path while collapsed details or Settings explain the decision.
12. **Format, profile and resolution are separate.** Format chooses MKV/MP4/Shareable MP4; the persistent Output profile chooses Auto/Original/High/Balanced/Compact per format; Resolution limit is only an optional per-job ceiling.
13. **Names should look like user files.** Downloads use source-derived filenames plus language/dub suffixes rather than cache-oriented names.
14. **Subtitle semantics and speech semantics differ.** Caption cues stay in subtitle files but are silently excluded from TTS input.
15. **Defaults should protect quality and hardware.** MKV Auto preserves source video; Shareable Auto targets compact predictable output; low-memory Macs get conservative model/context/recovery limits; no heavy source-separation model is introduced silently.
16. **Uncertainty beats fabricated content.** ASR recovery may leave a gap when evidence is weak; the UI should report the safeguard rather than quietly inserting plausible text.
17. **Stable perceived loudness matters.** A dubbed soundtrack should not become dramatically louder merely because no DubLocal line is active at that moment.
18. **Timing should follow the source window.** Variable per-line speech speed is preferable to a single global TTS speed, but pathological changes should be surfaced rather than hidden.
19. **Advanced diagnostics are available but not dominant.** Paths, hashes, context allocation and raw consoles remain accessible without occupying the normal workflow.
20. **No feature loss for simplification.** Reducing visual clutter must not remove valid capabilities or break earlier stages.
21. **A failure belongs to one layer.** Translation failure must not hide a completed subtitle file; export failure must not invalidate a voice WAV; model management must not block source inspection.
22. **Production copy describes user intent, not implementation history.** Use terms such as Standard workflow, Start Processing, Outputs, Options, Output files, Resolution limit and Audio & delivery. Historical/internal identifiers may remain in code when renaming them would create unnecessary migration risk, but they should not leak into the visible product.
