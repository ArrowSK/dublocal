# DubLocal changelog

DubLocal is still in active development. Versions below describe development builds from `main`.

> **Current development build:** `v0.6.0.dev0` — **Magic Flow UX**
>
> There is no packaged GitHub Release yet. Development builds update from official `main` inside DubLocal.

## v0.6.0.dev0 — Magic Flow UX — current

v0.6 turns the mature local pipeline into a simpler product-facing workflow while keeping detailed controls available.

### Authenticated course / website import

- Added **Course / Website** as a third source in Simple Magic Flow rather than a parallel processing workflow.
- Added a normalized `SourceProvider` / local `AcquiredMedia` boundary so authenticated acquisition ends before transcription, translation, TTS, mixing or export begins.
- Added a dedicated local Chromium profile for website sign-in; credentials are entered directly on the website rather than into DubLocal.
- Added a Domestika adapter plus a generic authenticated-video fallback for ordinary non-DRM media pages.
- Added course/lesson discovery, multiselect, sequential processing, per-lesson failure isolation and persistent resume state.
- Completed lessons are not reprocessed on resume; failed/cancelled lessons remain selectable.
- Course outputs are organized under `~/Movies/DubLocal/<Provider>/<Course>/` while acquired source media remains temporary job-cache data by default.
- Added explicit DRM/encrypted-stream detection/refusal. The importer contains no Widevine/FairPlay/PlayReady circumvention path.
- Added an **Authenticated Websites** Settings section for explicit browser preparation and local session clearing.
- Added direct single-lesson Course / Website input to Advanced while keeping full-course selection in Simple.
- The existing Stop/cleanup lifecycle now covers authenticated acquisition and course queues as well.
- Added safety policy so an explicit empty lesson selection never expands to all lessons and persisted/rendered import errors redact reusable signed-URL credentials.

### Magic Flow

- Added a new default **Magic Flow** at the top of Main.
- Normal inputs are reduced to source, rights confirmation, output language and desired outputs.
- One **Run Magic Flow** action resolves prerequisites and executes the existing local pipeline.
- Users can independently request subtitles, translation, voice-over and/or an output media file.
- Downstream choices imply their required upstream stages, so a dub automatically gets the subtitle and translation timeline it needs.

### Automatic subtitle-route recommendation

Magic Flow recommends the safest ready route rather than simply choosing the first caption it sees:

1. creator/embedded text subtitles;
2. already-installed Accurate Large-v3-Turbo-Q5 local transcription;
3. existing automatic captions;
4. another already-installed Whisper model.

Magic Flow never silently downloads a large AI model. Missing resources are explained and remain explicit Model Manager actions.

### Simple, medium and detailed UX

- The default Magic Flow stays compact.
- A collapsed **More options** section exposes subtitle strategy, original-audio retention, MKV/MP4 and video quality.
- The existing Source → Subtitles → Translate → Voice-over → Export workflow remains below for stage-by-stage control.
- Existing detailed stages remain individually collapsible.

### Auto source-language handoff

- Fixed the detailed workflow so a language detected by **Transcribe locally → Auto** is consumed by Translate when **From = Auto** remains selected.
- When no reliable cached language exists, contextual translation is allowed to perform its own local Qwen language identification instead of rejecting Auto.
- Legacy OPUS gives a clear manual-language requirement because it has no contextual detector.

### Commercial-facing output behavior

- Magic Flow uses meaningful source-derived filenames.
- MKV and Original/best quality are the recommended defaults.
- Original audio can be retained as a separate selectable track.
- Translation without voice can still produce a media package with selectable original/translated subtitles and untouched source audio.
- The processing engines are shared with the detailed workflow; Magic Flow is orchestration, not a second implementation.

## v0.5.3.dev0 — M5 Stabilization

### More stable dubbed loudness

- The original soundtrack stays at a reduced, stable bed level instead of returning to full programme loudness between DubLocal lines.
- Source subtitle dialogue/singing windows receive deeper attenuation.
- Gentle compression and limiting reduce distracting level jumps without claiming source separation.

### Closer per-line timing

- Voice remains anchored to each source subtitle start/end window.
- DubLocal chains legal FFmpeg `atempo` stages for an effective 0.30×–2.50× correction range.
- A small correction pass compensates for duration rounding.
- Subtitle timestamps are never rewritten by TTS timing.

### Original media + subtitles only

- Added **Package original + subtitles · no dub**.
- Original audio remains untouched.
- Local Original quality remains stream-copy by default.

### Smarter missing-word recovery without reopening ghosting

- Kept the anti-hallucination/repetition guard as the first defence.
- Added selective rechecks of suspicious sparse subtitle regions and short internal gaps.
- Recovery is accepted only when two isolated no-context decodes agree closely.
- Neighbour-echo candidates are rejected.
- Apple Silicon below 12 GiB is capped at 3 recovery regions / 24 seconds per transcription.

### M1-class compatibility

- No new source-separation, diarization or ASR model is required.
- Timing and loudness work is FFmpeg DSP.
- Smart transcript recovery reuses the already-selected Whisper model for short ranges only.
- Hardware-aware Qwen translation profiles remain unchanged.

## v0.5.2.dev0 — Transcription + Timing Reliability

- Added optional whisper.cpp Silero VAD for supported non-music transcription paths.
- Added no-context/repetition protection for Accurate music transcription and isolated recovery/suppression of severe repeated hallucination storms.
- Added variable per-line timing with a small onset cushion.
- Added contextual `From = Auto` language identification support.

## v0.5.1.dev0 — Voice Match + Export Refinement

- Added **Auto · match original vocal range** using lightweight source-audio F0 analysis and per-segment Kokoro voice presets.
- Strengthened original dialogue/singing suppression across complete subtitle windows.
- Embedded generated original + translated subtitles as selectable tracks by default.
- Added YouTube resolution selection and explicit local VideoToolbox downscaling while keeping local Original as the no-recode default.

## v0.5.0.dev0 — M5 Local Dubbed Media Export

- Connected subtitle, translation and Kokoro stages into end-to-end dubbed-media export.
- Added media-derived subtitle filenames.
- Strengthened contextual gender/reference, idiom/phraseology and metaphor handling.
- Kept caption cues in subtitles while removing them from temporary TTS input.
- Added timing fit, soundtrack ducking/mix, Replace/Add audio modes and video stream-copy.

## v0.4.2.dev0 — Subtitle Export + Translation Quality Pass

- Made subtitle output first-class: SRT default with VTT/TXT conversion without rerunning transcription.
- Added optional Accurate Large-v3-Turbo-Q5 Whisper model for difficult source audio.
- Added hardware-aware **Recommended for this Mac** contextual translation profiles.
- Kept legacy OPUS as an explicit small/fast option.
- Added protected subtitle tags, runtime/prompt leakage rejection, wrong-script validation and strict subtitle-ID/timestamp integrity.

## v0.4.1.dev0 — M3.1 Contextual Translation

Introduced the first Qwen3 contextual translation path with nearby dialogue, programme-wide context and rolling translated terminology/style memory.

## v0.4.0.dev0 — M4 Local Voice

- Added Kokoro as the first local TTS backend.
- Reused compatible existing Kokoro environments through isolated worker processes.
- Added local voice-only WAV generation from source or translated SRT.

## v0.3.0.dev0 — M3 Local Translation

- Added pinned local Helsinki-NLP OPUS/Marian subtitle translation.
- Preserved timestamps and side-by-side subtitle review.

## v0.2.0.dev0 — M2 Local Transcription

- Added local `whisper.cpp` transcription, Model Manager, language selection/detection and timestamped SRT output.
- Added the first in-app updater.

## v0.1.0.dev0 — M1 Source and Captions

- Added local media inspection with ffprobe.
- Added YouTube metadata/caption discovery with yt-dlp.
- Added existing subtitle/caption extraction and the branded macOS launcher.
