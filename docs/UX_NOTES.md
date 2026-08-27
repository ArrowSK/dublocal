# DubLocal UX principles

This document captures the product-facing UX rules for `v0.5.3.dev0`.

1. **Main is a workflow, not a control panel.** The primary path is `1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export`. Model/runtime detail belongs in Settings or collapsed diagnostics.
2. **Progressive disclosure.** A user can stop after subtitles, translation, voice generation or final export. Later stages must never be required to retrieve an earlier useful output.
3. **Packaging is independent from dubbing.** Export must support original media + source subtitles without requiring translation or TTS.
4. **Persistent stage state.** Source loading, transcription, translation, voice generation and export keep clear success/failure state on the same stage card. Toasts are supplemental.
5. **One visual language.** Green remains the product accent; framework defaults should not reintroduce unrelated orange states.
6. **Visible version.** Settings shows the actual running DubLocal version near the top.
7. **Long operations report meaningful progress.** Downloads, transcription, translation, TTS and render/remux expose percentage/ETA when the underlying operation permits it. Do not invent fake precision.
8. **Automatic choices must remain explainable.** Hardware-aware model recommendations, Auto source-language resolution and Auto voice matching simplify the normal path while collapsed details explain the decision.
9. **Names should look like user files.** Downloads use source-derived filenames plus language/dub suffixes rather than cache-oriented names.
10. **Subtitle semantics and speech semantics differ.** Caption cues stay in subtitle files but are silently excluded from TTS input.
11. **Defaults should protect quality and hardware.** Local Original video stays stream-copy; low-memory Macs get conservative model/context/recovery limits; no heavy source-separation model is introduced silently.
12. **Uncertainty beats fabricated content.** ASR recovery may leave a gap when evidence is weak; the UI should report the safeguard rather than quietly inserting plausible text.
13. **Stable perceived loudness matters.** A dubbed soundtrack should not become dramatically louder merely because no DubLocal line is active at that moment.
14. **Timing should follow the source window.** Variable per-line speed is preferable to a single global TTS speed, but pathological stretching should be surfaced rather than hidden.
15. **Advanced diagnostics are available but not dominant.** Paths, hashes, context allocation and raw consoles remain accessible without occupying the normal workflow.
16. **No feature loss for simplification.** Reducing visual clutter must not remove valid capabilities or break earlier stages.
17. **A failure belongs to one layer.** Translation failure must not hide a completed subtitle file; export failure must not invalidate a voice WAV; model management must not block source inspection.
