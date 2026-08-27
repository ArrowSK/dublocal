# DubLocal UX principles

This document captures the product-facing UX rules for `v0.5.0.dev0`.

1. **Main is a workflow, not a control panel.** The primary path is `1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export`. Detailed engine/model state belongs in Settings or collapsed diagnostics.
2. **Progressive disclosure.** A user can stop after subtitles, after translation, after voice generation or after final export. Later stages must never be required just to retrieve an earlier useful output.
3. **Persistent stage state.** Source loading, transcription, translation, voice generation and export keep a clear success/failure status on the same card. Transient browser notifications are supplemental only.
4. **One visual language.** Green remains the only product accent. Framework/browser orange accents and unrelated warning colors should not dominate the interface.
5. **Visible version.** Settings always shows the running DubLocal version near the top.
6. **Long operations report progress.** Downloads, transcription, contextual translation, TTS and M5 render/remux operations expose percentage/ETA when the underlying operation provides meaningful measurable progress. Short atomic operations should not invent fake precision.
7. **Automatic choices must remain explainable.** Hardware-aware model recommendations and source-language detection should make the normal path simpler, while collapsed details expose what was detected and why.
8. **Names should look like user files, not cache artifacts.** Downloads use media-derived filenames plus language suffixes instead of generic names such as `captions.srt`.
9. **Subtitle semantics and speech semantics are different.** Caption cues remain in subtitle files but are silently excluded from TTS input. The UI should not require users to edit SRTs merely to stop Kokoro reading `[MUSIC]` aloud.
10. **Defaults should be safe and practical.** M5 defaults to a dubbed primary mix and recommends MKV. Video is stream-copied when possible; DubLocal does not silently trigger a long video transcode to satisfy MP4.
11. **Advanced diagnostics are available but not dominant.** Executable paths, model hashes, context allocation and raw activity consoles remain accessible without occupying the normal workflow.
12. **No feature loss for simplification.** Reducing visual clutter must not remove existing valid controls or break working earlier stages.
13. **A failure belongs to one layer.** Translation failure should not hide a completed subtitle file; M5 failure should not invalidate the generated voice WAV; a model-manager problem should not prevent source inspection.
