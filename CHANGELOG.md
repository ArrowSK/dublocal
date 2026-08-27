# DubLocal changelog

DubLocal is still in active development. Versions below describe development builds from `main`.

> **Current development build:** `v0.5.2.dev0` — **Transcription + Timing Reliability**
>
> There is no packaged GitHub Release yet. The first packaged release will be published after Mac distribution/release validation is ready.

## v0.5.2.dev0 — Transcription + Timing Reliability — current

v0.5.2 focuses on two real-world failures found during music-video testing: Whisper hallucinating speech over non-vocal audio, and dubbed speech starting/ending noticeably differently from the source subtitle timing.

### Anti-hallucination local transcription

- Added the official whisper.cpp **Silero VAD v6.2.0** auxiliary speech detector when the installed `whisper-cli` supports VAD.
- The VAD model is approximately 0.9 MiB, MIT licensed, pinned to upstream revision `9ffd54a1e1ee413ddf265af9913beaf518d1639b` and verified against SHA-256 `2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987`.
- The auxiliary model is downloaded on demand; if it cannot be obtained offline, transcription still works with conservative decoder settings.
- VAD processing limits Whisper to detected speech regions, reducing invented dialogue during instrumental intros/silence and long repetition loops over non-speech material.
- Long-form text carry-over is capped at 64 tokens and the no-speech threshold is slightly stricter to reduce self-reinforcing decoder repetition.
- The Model Manager status reports whether the speech detector is installed or will be prepared on demand.

### Variable per-line dub timing

- Replaced the previous “speed up only when overflowing” behavior with per-segment duration matching.
- Each Kokoro segment is fitted independently to its subtitle time window.
- Short generated speech can be slowed and long generated speech accelerated through FFmpeg `atempo` so the dub ends approximately with the source subtitle line.
- A small onset cushion prevents translated speech from consistently jumping in fractionally before the original line.
- Tempo changes are limited to 0.5×–2.0×; more extreme stretches are reported rather than forced into obviously damaged speech.
- Timing fitting remains an export-layer operation and does not modify the SRT timestamps.

### Validation

- Added regression tests for VAD command wiring, conservative Whisper decoder options, slow/fast line fitting, onset alignment and extreme-stretch reporting.
- Documentation/version guards updated for v0.5.2.

## v0.5.1.dev0 — Voice Match + Export Refinement

- Added **Auto · match original vocal range** using lightweight source-audio F0 analysis and per-segment Kokoro voice presets.
- Strengthened original dialogue/singing suppression across complete subtitle windows.
- Embedded generated original + translated subtitles as selectable tracks by default.
- Added YouTube resolution selection and explicit local VideoToolbox downscaling while keeping local Original as the no-recode default.

## v0.5.0.dev0 — M5 Local Dubbed Media Export

- Connected the subtitle, translation and Kokoro stages into end-to-end dubbed-media export.
- Added reliable source-language propagation and media-derived subtitle filenames.
- Strengthened contextual gender/reference, idiom/phraseology and metaphor handling.
- Kept caption cues in subtitles while removing them from temporary TTS input.
- Added timing fit, soundtrack ducking/mix, Replace/Add audio modes and video stream-copy.

## v0.4.2.dev0 — Subtitle Export + Translation Quality Pass

- Made subtitle output first-class: SRT default with VTT/TXT conversion without rerunning transcription.
- Added optional Accurate Large-v3-Turbo-Q5 Whisper model for difficult source audio.
- Added hardware-aware **Recommended for this Mac** contextual translation profiles.
- Low-memory Apple Silicon uses Qwen3 4B with reduced llama.cpp context allocation; stronger Macs use Qwen3 8B, with a senior review pass on the Best-quality profile.
- Kept legacy OPUS as an explicit small/fast option.
- Added protected subtitle tags, runtime/prompt leakage rejection, wrong-script validation and strict subtitle-ID/timestamp integrity.

## v0.4.1.dev0 — M3.1 Contextual Translation

Introduced the first Qwen3 contextual translation path with nearby dialogue, programme-wide source context and rolling translated terminology/style memory. Real-language testing showed that Qwen3 4B alone was not a universal top-quality choice, which led to the adaptive 4B/8B v0.4.2 architecture.

## v0.4.0.dev0 — M4 Local Voice

- Added Kokoro as the first local TTS backend.
- Reused compatible existing Kokoro environments through isolated worker processes.
- Added local voice-only WAV generation from source or translated SRT.
- Added per-segment assets, timing manifest and overflow diagnostics.

## v0.3.0.dev0 — M3 Local Translation

- Added pinned local Helsinki-NLP OPUS/Marian subtitle translation.
- Preserved timestamps and side-by-side subtitle review.
- Added shared Hugging Face cache and compatible external runtime reuse.

## v0.2.0.dev0 — M2 Local Transcription

- Added local `whisper.cpp` transcription.
- Added model management, language selection/detection and timestamped SRT output.
- Added YouTube/local-file transcription fallback and the first in-app updater.

## v0.1.0.dev0 — M1 Source and Captions

- Added local media inspection with ffprobe.
- Added YouTube metadata/caption discovery with yt-dlp.
- Added existing subtitle/caption extraction and the branded macOS launcher.
