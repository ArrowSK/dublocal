# DubLocal changelog

DubLocal is still in active development. Versions below describe development builds from `main`.

> **Current development build:** `v0.5.1.dev0` — **Voice Match + Export Refinement**
>
> There is no packaged GitHub Release yet. The first packaged release will be published after Mac distribution/release validation is ready.

## v0.5.1.dev0 — Voice Match + Export Refinement — current

v0.5.1 refines the working v0.5 end-to-end export path without redesigning the earlier workflow.

### Automatic voice matching

- **Auto · match original vocal range** is the normal Main voice choice.
- DubLocal performs a lightweight local F0/range analysis over the source primary audio inside subtitle windows.
- Lower/higher source vocal ranges map to contrasting Kokoro voice presets when the selected language provides them.
- Mixed lower/higher material can therefore use two voices segment-by-segment while keeping one Kokoro model/language pipeline loaded.
- This is acoustic preset matching, not speaker identity or gender-identity inference.
- Manual Kokoro voice selection remains available.

### Stronger original dialogue/singing suppression

- The source subtitle timeline now guides soundtrack suppression when available.
- Original audio stays strongly reduced across the complete source dialogue/singing window, including gaps after a shorter translated TTS line ends.
- Nearby subtitle windows are merged to reduce audible pumping.
- Sidechain compression remains as secondary protection around generated voice.
- When no usable source timeline exists, DubLocal uses a stronger voice-driven fallback.
- This remains ducking/overlay, not professional dialogue-free M&E separation or neural source separation.

### Selectable subtitle tracks in exported media

- Generated original/source subtitles and translated subtitles are embedded by default when available.
- They remain selectable tracks and are never burned into video.
- MKV preserves source subtitle streams and adds DubLocal tracks.
- MP4 packages generated SRT tracks as `mov_text`.
- Subtitle language/title/disposition metadata is set independently.

### Video quality selection

- Added **Original / best available**, 2160p, 1440p, 1080p, 720p and 480p maximum quality choices.
- YouTube uses the selection as a maximum source height before download, then stream-copies the chosen video during remux.
- Local files keep **Original** as the no-recode default.
- Selecting a lower local resolution explicitly opts into H.264 VideoToolbox re-encoding.
- DubLocal does not silently downscale or upscale local media.

### Documentation and validation

- README, User Guide, Installation, Architecture and Troubleshooting now describe v0.5.1 behavior and limitations.
- Regression tests cover automatic voice selection/F0 bucketing, timeline-driven suppression, subtitle mux mapping/metadata, YouTube max-height selection and explicit local VideoToolbox downscale.

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
