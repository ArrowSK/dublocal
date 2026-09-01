# DubLocal changelog

DubLocal is still in active development. Versions below describe development/beta builds from `main`.

> **Current beta:** `v0.6.0b8` — **production architecture cleanup**
>
> Beta 8 consolidates the active runtime into explicit production services, removes import-time function/class and Gradio-constructor replacement from the running application path, and folds authenticated-source safety policy into the canonical provider while preserving the established user workflows.

## v0.6.0b8 — Production architecture cleanup — current

- Replaced the accumulated active overlay/installer composition with one explicit launcher and production UI composition root.
- Standard, Advanced, batch, course, transcription, translation, voice, audio and export stages now connect through ordinary service calls rather than import-time function/class replacement.
- Package import is side-effect free and limited to package metadata.
- Added architecture regression tests that reject assignment into imported production modules and Gradio constructors.
- Kept contextual Qwen adaptive batching, Auto source detection, subtitle-ID/script validation, bounded recovery and local translation cache behavior on the canonical translation path.
- Made Whisper VAD fallback, repetition protection and smart recovery direct stages of canonical transcription.
- Kept native voice timing, Hungarian/Russian/custom TTS routing, automatic vocal-range matching, adaptive audio mixing and format-aware output profiles behind explicit service boundaries.
- Folded authenticated-source credential redaction, signed-manifest DRM inspection, non-secret query routing and explicit-empty lesson selection semantics into `authenticated_web.py` itself; removed the now-obsolete runtime policy overlay.
- Fixed the Standard local-file queue UI callback so both the queue summary and processing-button label are updated through the declared Gradio outputs.
- Historical compatibility modules that are no longer part of active production composition remain dormant for incremental removal instead of being deleted in a risky bulk rewrite.

## v0.6.0b7 — Cross-platform Hungarian voice-over

- Added Hungarian as a complete translation → voice-over target in the existing Standard workflow.
- On macOS, Auto prefers an installed `hu_HU` system voice while keeping Piper voices selectable.
- On Windows and other platforms, Hungarian uses Piper only; no Apple-only dependency is required by the provider backend.
- Added Piper Anna, Berta and Imre with pinned voice-repository revision and local model/config integrity verification.
- Added a dedicated Piper runtime environment so GPL Piper is invoked out of process rather than imported into DubLocal's Apache-2.0 application runtime.
- Kept preparation explicit: a processing job does not silently install Piper or download a Hungarian voice model.
- Hungarian synthesis follows the timed-SRT contract and regenerates only materially overflowing lines at a faster native speaking rate.
- Added provider-neutral voice progress copy and Windows CI portability coverage.
- Added explicit documentation that macOS system voices are OS-provided and DubLocal does not assert separate commercial/redistribution rights for their output.

## v0.6.0b6 — Contextual translation performance

- Added fragmentation-aware optimistic translation batches: normal sentence-sized subtitles keep the established 48/36 limits, while very dense short-caption timelines can begin at 96 lines on Qwen3 8B or 72 on 4B.
- Kept the existing adaptive safety ladder: any larger attempt that fails strict alignment is retried at half size until the established 12-line floor and bounded recovery path take over.
- Runtime context allocation now follows the programme context budget actually used by the prompt, plus existing generation/headroom, instead of reserving a much larger KV cache simply because the hardware recommendation allows it.
- Added conditional llama.cpp `--cache-reuse 64` support detection. Older runtimes keep the established server command unchanged.
- Kept the same hardware-selected Qwen model, prompt text, sampling, review policy, target-language validation and refusal to write ambiguously aligned SRT output.
- Added regression coverage for dense/normal batch selection, programme-context allocation, conditional prompt reuse and restoration of compatibility state after each translation call.

## v0.6.0b5 — Format-aware output profiles and production UI

- Added persistent **Settings → Output profiles** for MKV, MP4 and Shareable MP4.
- Added **Auto**, **Original**, **High**, **Balanced** and **Compact** profiles with format-specific Auto behavior rather than one global compromise.
- MKV Auto resolves to Original/preservation behavior; MP4 Auto resolves to Balanced up to 1080p; Shareable MP4 Auto resolves to Compact up to 720p.
- Replaced the old 480p Shareable target of 2.5 Mbps video + 192 kbps audio with a compact Auto target of 500 kbps H.264 + 96 kbps AAC, about 4.5 MB/minute.
- Burned and selectable Shareable MP4 outputs now use the same saved profile policy.
- MP4/Shareable output can re-encode when source codec, pixel format, resolution or bitrate would defeat the selected profile, while already-efficient compatible streams can still be copied.
- Explicit per-job resolution remains an additional ceiling rather than being confused with compression quality.
- Renamed the primary product surface from **Magic Flow** to **Standard workflow**, **Simple** to **Standard**, and **Run Magic Flow** to **Start Processing**.
- Tightened related production labels: **Outputs**, **Options**, **Output files**, **Resolution limit**, and **Audio & delivery**.
- Kept internal compatibility names stable where a mechanical rename would create migration risk.
- Added regression coverage for format-specific Auto behavior, 480p/720p compact sizing, MKV preservation, MP4 compatibility/size re-encoding, saved overrides and production UI terminology.

## v0.6.0b4 — Subtitle burn-in reliability

- Detects whether the exact FFmpeg binary used for burn-in exposes the `subtitles` filter before encoding begins.
- Uses normal FFmpeg when it supports subtitle rendering and otherwise looks for the side-by-side, keg-only Homebrew `ffmpeg-full` binary.
- Packaged setup/update can offer `ffmpeg-full` without uninstalling or replacing core FFmpeg.
- Keeps the VideoToolbox → `libx264` retry for genuine H.264 encoder failures.
- A missing `subtitles` filter no longer triggers a pointless second encode with a different H.264 codec.
- Preserves the standalone SRT and reports the actual missing capability when no subtitle-capable FFmpeg is available.
- Added regression coverage for normal/full FFmpeg selection, missing-filter refusal, encoder fallback and the reported `Filter not found` path.

## v0.6.0b3 — Adaptive long-form translation

- Added an optimistic fast path: Qwen3 8B starts with up to 48 subtitle lines per model call and Qwen3 4B with up to 36.
- A failed large batch is not sent through expensive whole-batch recovery. DubLocal retries only that section at half size, down to the established 12-line safety floor.
- After two clean smaller batches, the batch size grows again automatically, so one difficult section does not slow the rest of a movie.
- The failed fast response is reused when the 12-line recovery floor is reached instead of spending another identical model call.
- Programme-wide/nearby context remains independent from output batch size, preserving contextual translation while reducing repeated prompt-prefill work.
- Progress messages now show subtitles completed and the next adaptive batch ceiling.
- Translation cache policy was changed so beta-2 cache entries are not mixed with the new adaptive execution strategy.
- Added regression tests proving a clean 96-subtitle timeline completes in two 48-line calls and that a bad 48-line section falls back 48→24, stabilizes, then grows back to 48.

## v0.6.0b2 — Contextual translation reliability

- Reduced contextual translation output batches from the beta-1 36–48-line optimization to moderate sizes, with a 12-line cap for highly fragmented subtitle timelines.
- Kept programme-wide and nearby context independent from output batch size, so the reliability fix does not turn contextual translation into isolated line-by-line translation.
- Added safe recovery for common Qwen numbering variants such as `1. text` and `ID 2: text`.
- Added exact positional recovery only when an ID-less response contains exactly one clean output line for every requested subtitle; ambiguous mappings are still refused.
- Focused missing-ID recovery on the source lines actually missing instead of resending the whole chunk as translation targets.
- Bumped contextual prompt/cache versioning so old cached translations do not mix with the new policy.
- Published the fix as a separate beta package rather than silently replacing the beta-1 DMG.

## v0.6.0b1 — First packaged macOS beta

### macOS beta package

- Added a reproducible macOS DMG builder and a real macOS CI packaging job.
- Added a conventional `DubLocal.app` with the established DubLocal `.icns` icon plus an Applications shortcut in the DMG.
- Added a first-launch bootstrap that keeps the managed application checkout under `~/Library/Application Support/DubLocal/app`.
- The bootstrap pins a new installation to the exact packaged Git revision, while retaining a normal official `main` Git checkout so the existing safe updater/restart architecture remains usable.
- The beta does not bundle AI models, authenticated-site browser state, Demucs or Whisper model data; these remain explicit local resources.
- Added native first-launch handling for missing Git/Python and optional FFmpeg preparation without requiring a terminal-driven installer flow.
- Added clear Gatekeeper instructions for the intentionally unsigned beta and explicitly avoids recommending global Gatekeeper disablement.
- The DMG includes license notices and a SHA-256 checksum artifact.

### Product branding

- Reused the established `assets/macos/DubLocal.svg` identity for the packaged app icon.
- Added the same DubLocal mark to the in-app header without redesigning the existing Simple/Advanced product UI.

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

### Storage & cleanup hardening

- Added centralized storage accounting and safe temporary cleanup.
- Added bounded log, course-manifest, repair-backup and stale browser-runtime housekeeping.
- Installed models, authenticated sessions and finished outputs remain protected from automatic/manual temporary cleanup.

### Magic Flow

- Added a default **Magic Flow** at the top of Main.
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
