# DubLocal changelog

DubLocal is still in active development. Versions below describe development builds from `main`.

> **Current development build:** `v0.5.3.dev0` — **M5 Stabilization**
>
> There is no packaged GitHub Release yet. Development builds update from official `main` inside DubLocal.

## v0.5.3.dev0 — M5 Stabilization — current

v0.5.3 is a real-world quality and reliability pass based on complete music-video dubbing tests. It keeps the existing workflow and avoids adding another heavy AI model.

### More stable dubbed loudness

- The original soundtrack now stays at a reduced, stable bed level instead of returning to full programme loudness whenever no DubLocal line is speaking.
- Source subtitle dialogue/singing windows receive deeper attenuation so the original vocal remains clearly behind the dub.
- Gentle compression and limiting reduce distracting level jumps without pretending the married source mix has been separated into dialogue and M&E stems.

### Closer per-line timing

- Voice remains anchored to the source subtitle start/end window.
- DubLocal can chain legal FFmpeg `atempo` stages for an effective **0.30×–2.50×** correction range instead of stopping at the previous 0.5×–2.0× single-stage range.
- A small correction pass compensates for duration rounding when the generated line still misses the target end by more than about 25 ms.
- Truly pathological stretches are still reported rather than forced, and subtitle timestamps are never rewritten by TTS timing.

### Original media + subtitles only

- Export now includes **Package original + subtitles · no dub**.
- This mode keeps original audio untouched, adds the current source/transcribed subtitle as a selectable track, and adds neither translated subtitles nor a DubLocal audio track.
- Local Original quality remains stream-copy by default; MKV remains the safest multi-track container.

### Smarter missing-word recovery without reopening ghosting

- The existing anti-hallucination/repetition guard remains the first line of defence; Whisper is not made globally more eager.
- DubLocal selectively rechecks only suspicious sparse subtitle regions and, for the Accurate music profile, short internal gaps bounded by real transcript text.
- A recovery is accepted only when **two isolated no-context decodes agree closely**.
- Candidate text that merely echoes neighbouring subtitles is rejected.
- Sparse-line replacement must add meaningful information while staying related to the original result.
- On Apple Silicon below 12 GiB, extra recovery is capped at **3 regions / 24 seconds** per transcription. There is no hidden second full-video pass.

### M1-class compatibility

- No new source-separation, diarization or transcription model is required.
- Timing and loudness work is FFmpeg DSP.
- Smart transcript recovery reuses the already-selected Whisper model for short targeted ranges only.
- Hardware-aware Qwen translation profiles remain unchanged, so an 8 GB M1 continues to use the lightweight contextual profile.

## v0.5.2.dev0 — Transcription + Timing Reliability

- Added the optional whisper.cpp Silero VAD auxiliary speech detector for supported non-music transcription paths.
- Added no-context/repetition protection for Accurate music transcription and isolated recovery/suppression of severe repeated hallucination storms.
- Added variable per-line timing with a small onset cushion.
- Fixed contextual `From = Auto` source-language resolution.

## v0.5.1.dev0 — Voice Match + Export Refinement

- Added **Auto · match original vocal range** using lightweight source-audio F0 analysis and per-segment Kokoro voice presets.
- Strengthened original dialogue/singing suppression across complete subtitle windows.
- Embedded generated original + translated subtitles as selectable tracks by default.
- Added YouTube resolution selection and explicit local VideoToolbox downscaling while keeping local Original as the no-recode default.

## v0.5.0.dev0 — M5 Local Dubbed Media Export

- Connected subtitle, translation and Kokoro stages into end-to-end dubbed-media export.
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

Introduced the first Qwen3 contextual translation path with nearby dialogue, programme-wide source context and rolling translated terminology/style memory.

## v0.4.0.dev0 — M4 Local Voice

- Added Kokoro as the first local TTS backend.
- Reused compatible existing Kokoro environments through isolated worker processes.
- Added local voice-only WAV generation from source or translated SRT.

## v0.3.0.dev0 — M3 Local Translation

- Added pinned local Helsinki-NLP OPUS/Marian subtitle translation.
- Preserved timestamps and side-by-side subtitle review.

## v0.2.0.dev0 — M2 Local Transcription

- Added local `whisper.cpp` transcription, model management, language selection/detection and timestamped SRT output.
- Added the in-app updater.

## v0.1.0.dev0 — M1 Source and Captions

- Added local media inspection with ffprobe.
- Added YouTube metadata/caption discovery with yt-dlp.
- Added existing subtitle/caption extraction and the branded macOS launcher.
