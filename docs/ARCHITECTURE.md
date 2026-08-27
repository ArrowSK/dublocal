# DubLocal architecture

**Current development build: v0.5.2.dev0 — Transcription + Timing Reliability**

DubLocal is a local-first media pipeline made from separable stages. The Gradio UI coordinates jobs, but source inspection, transcription, translation, TTS, timing, mixing and remuxing remain independent modules with explicit failure boundaries.

## Pipeline

```text
YouTube / local media
        ↓
inspection + caption discovery
        ↓
existing text subtitles OR local whisper.cpp transcription
  └─ v0.5.2: Silero VAD speech gating when supported
        ↓
normalized Segment[] timeline
        ├──────────────→ SRT / VTT / TXT export
        ↓ optional
contextual translation
  ├─ Recommended for this Mac
  │    ├─ Qwen3 4B lightweight
  │    └─ Qwen3 8B balanced / best + optional review
  └─ Fast legacy · OPUS/Marian
        ↓
source or translated SRT
        ↓
TTS preparation
  ├─ preserve subtitle file
  └─ remove caption cues from temporary speech input
        ↓
Kokoro TTS
  ├─ manual voice OR automatic vocal-range matching
  ├─ one Kokoro pipeline/model
  ├─ per-segment voice preset selection
  ├─ per-segment WAVs
  └─ synchronized voice-only WAV + manifest
        ↓
v0.5.2 timing fit
  ├─ each line targets its own subtitle time window
  ├─ short lines may slow; long lines may accelerate
  └─ quality guard: 0.5×–2.0× atempo range
        ↓
v0.5.1+ soundtrack mix
  ├─ source subtitle windows drive strong original-dialogue suppression
  └─ translated voice overlaid into AAC dubbed mix
        ↓
track-aware remux/export
  ├─ Replace primary audio — default
  ├─ Add dubbed audio as second track
  ├─ embed generated original + translated subtitles
  ├─ YouTube max-resolution source selection
  └─ local stream-copy by default / explicit VideoToolbox downscale
```

## Core design rules

1. Subtitle IDs and timestamps are stable data. Translation changes text, not timing.
2. Subtitles are a complete output. Translation, TTS and export remain optional downstream stages.
3. Contextual translation treats subtitle fragments as continuous discourse.
4. Hardware recommendations scale both model choice and actual llama.cpp context/KV allocation.
5. Caption cues remain subtitle data but are not translated as dialogue and are not spoken by TTS.
6. Heavy models download only after explicit user action. Tiny auxiliary reliability assets may be prepared on demand and checksum-verified.
7. Reuse system executables, shared model caches and compatible external runtimes before installing duplicates.
8. Never merge Python virtual environments or inject another application's `site-packages` into DubLocal.
9. No silent cloud fallback and no silent downgrade from contextual translation to OPUS.
10. Translation must pass alignment/runtime-leakage/target-script validation before SRT output.
11. One failed backend must not invalidate simpler completed stages.
12. Video re-encoding is never implied merely by audio/subtitle changes.
13. Local-file export defaults to stream-copy. Re-encoding occurs only after an explicit lower-resolution selection.
14. Automatic voice matching must stay lightweight: no extra TTS model, diarization model or source-separation model is required.
15. Acoustic voice matching is preset selection, not speaker identity or gender-identity classification.
16. ASR output from non-speech audio is treated as a recognition failure, not content to be translated. Speech gating and conservative long-form decoding are preferred over post-hoc guessing.
17. Dub timing may change generated audio duration, but it does not move subtitle timestamps.

## Normalized subtitle timeline

`src/dublocal/timeline.py` defines:

```text
Segment
  index: int
  start_ms: int
  end_ms: int
  text: str
```

Integer milliseconds avoid accumulated timing drift. `subtitle_export.py` converts this stable timeline to SRT, WebVTT or TXT without rerunning transcription. `output_naming.py` exposes media-derived names such as `Movie Name.en.srt`, `Movie Name.ru.srt` and `Movie Name.dub.ru.mkv` while internal job files remain disposable.

## Transcription and anti-hallucination policy

`transcription.py` manages `whisper-cli`, FFmpeg speech preparation, optional Whisper weights and the v0.5.2 auxiliary VAD path. Base is the normal default; Large-v3-Turbo-Q5 is the optional higher-accuracy path for songs, accents, noisy material or damaged automatic captions.

Long-form music/video transcription can fail in two characteristic ways: hallucinated text over silence/instrumental audio, and self-reinforcing repetition after a short phrase. v0.5.2 addresses the source of those failures rather than filtering arbitrary text after recognition:

- feature-detect whether the installed `whisper-cli` supports VAD;
- prepare the official whisper.cpp Silero VAD v6.2.0 model on demand;
- verify the pinned model SHA-256 before use;
- process only detected speech regions when VAD is available;
- use a 64-token carried-text context cap;
- use a slightly stricter no-speech threshold;
- retain normal transcription when an older CLI has no VAD or the tiny auxiliary model cannot be downloaded offline.

The VAD model is an auxiliary speech detector, not another transcription model. It is approximately 0.9 MiB and does not materially change Mac memory requirements.

`language_utils.py` normalizes common ISO codes/full labels so detected language can populate Translate → From. Loading a new source clears stale language state.

## Adaptive contextual translation

The contextual path is split across:

```text
hardware_profile.py            architecture/RAM detection + recommendation tier
adaptive_contextual.py         choose/register Qwen3 4B or Qwen3 8B
contextual_runtime.py          adaptive llama-server/llama-cli lifetime
contextual_policy.py           chunk/context plan + translation/review prompts
contextual_progress.py         orchestration/recovery/review/SRT writing
translation_quality.py         protected tags + output validation
contextual_recovery.py         strict ID-oriented recovery
```

Current conservative profiles are:

```text
Apple Silicon < 12 GB     Qwen3 4B · review off · 8,192 input cap
Apple Silicon 12–23 GB    Qwen3 8B · review off · 16,384 input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · 24,576 input cap
Intel < 24 GB             Qwen3 4B · review off · 6,144 input cap
Intel 24 GB+              Qwen3 8B · review off · 12,288 input cap
```

The prompt/review explicitly covers speaker/addressee/reference relationships, grammatical gender where supported, idioms/phraseology, metaphor fidelity, terminology continuity, slang/profanity and recurring refrains. Standalone caption tags bypass translation and are copied exactly.

## TTS preparation and automatic vocal-range matching

`voice_text.py` creates a temporary speech-only SRT. `[MUSIC]` becomes silence; `[LAUGHS] Hello` becomes spoken `Hello`. The original subtitle file is unchanged.

`tts.py` and `kokoro_worker.py` generate per-segment WAVs, a synchronized voice-only WAV and `voice-manifest.json`. Compatible external Kokoro environments are invoked through their own Python process; they are never imported into DubLocal's interpreter.

`voice_match.py` is the lightweight casting layer. It decodes the original primary audio to low-rate mono analysis data, estimates dominant fundamental frequency inside subtitle windows, maps lower/higher ranges to available Kokoro presets, and stores the selected voice per segment. One Kokoro model/pipeline stays loaded; changing voice presets does not double model memory.

The matcher is acoustic preset selection, not speaker identification or gender-identity classification. If analysis is inconclusive or the selected language exposes only one usable voice, the normal Kokoro default is used.

## v0.5.2 per-line timing fit

`m52.py` installs the current timing fitter into the stable `m5.fit_voice_timing` API before the Gradio app is built. `m51.render_dubbed_media()` therefore uses the refined fitter without requiring another export API or a redesign of the working UI.

For every generated segment:

1. read original subtitle `start_ms` / `end_ms` and generated WAV duration from `voice-manifest.json`;
2. reserve a small 35–100 ms onset cushion so synthesized speech does not sound systematically early;
3. use the remainder of the subtitle window as the target spoken duration;
4. calculate `atempo = generated_duration / target_duration`;
5. slow short speech or accelerate long speech as needed;
6. constrain the factor to 0.5×–2.0×;
7. assemble the fitted segments at their adjusted starts into a new synchronized voice track;
8. report residual mismatch when an extreme line cannot be fitted inside the quality guard.

The target for normal lines is therefore the subtitle end time, rather than merely “do not overflow.” Subtitle/SRT timestamps are never rewritten by this process.

## Stronger dialogue/singing suppression

Professional dubbing ideally uses a dialogue-free Music & Effects stem. Ordinary consumer media often provides only a married mix, so DubLocal cannot perfectly isolate original dialogue without source separation.

`m51.py` uses the **source subtitle timeline** as the practical suppression guide:

- nearby source dialogue/singing windows are merged to reduce pumping;
- original audio is strongly attenuated across the complete source window, not only while synthesized TTS is non-silent;
- sidechain compression remains as a fallback/protection when a usable source timeline is unavailable.

This is intentionally described as suppression/ducking, not source separation.

## Subtitle muxing and video quality

`m51.py` also owns the v0.5.1 track-aware export refinements.

When available, generated original/source subtitles and translated subtitles are embedded by default as selectable streams and are never burned into the video. MKV can preserve existing source subtitle streams and add the DubLocal tracks; MP4 packages generated SRT streams as `mov_text`.

Export quality options are:

```text
Original / best available
2160p maximum
1440p maximum
1080p maximum
720p maximum
480p maximum
```

For YouTube, the selected value constrains yt-dlp source acquisition before final remux. For local media, Original means `-c:v copy`; selecting a lower resolution explicitly opts into H.264 VideoToolbox re-encoding. DubLocal never silently downscales or upscales local media.

## Export modes

**Replace primary audio — default**: the DubLocal mix becomes primary/default audio; additional original audio streams are retained where possible.

**Add dubbed audio as second track**: original audio streams remain untouched and DubLocal is appended as another selectable track.

MKV remains the recommended container. MP4 is used only when requested streams can be packaged compatibly. Audio processing/re-encoding of the new mix does not imply video re-encoding.

## UI layering

`ui.py` remains the stable earlier workflow implementation. `ui_v042.py` adds hardware-adaptive translation policy. `ui_v050.py` now contains the v0.5/v0.5.1 workflow adapters: reliable language propagation, readable filenames, speech-only TTS preparation, automatic voice matching and the Export stage. v0.5.2 intentionally leaves this working layout intact; `m52.py` changes timing behavior behind the existing export API.

Main remains:

```text
1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export
```

Settings remains:

```text
Updates | Model Manager | Local Resources
```

## Temporary jobs and dependency reuse

`dependencies.py` reports/reuses FFmpeg/ffprobe, whisper.cpp, llama.cpp, shared Hugging Face cache and compatible external Python environments.

`job_cache.py` owns temporary cleanup:

```text
root       ~/Library/Caches/DubLocal/jobs/
max age    24 hours
max size   4 GiB
strategy   age first, then oldest-first size pruning
```

Temporary YouTube downloads, voice-analysis audio, fitted voice, subtitle conversion, dubbed mixes and remux outputs are covered by the same lifecycle. Persistent Whisper/VAD/Qwen/Kokoro assets and the shared Hugging Face cache are outside it.

## Still out of scope

- OCR for image subtitle streams;
- full speaker diarization/identity tracking;
- professional dialogue/M&E source separation;
- semantic rephrasing specifically to fit extreme dub timing;
- signed/notarized macOS packaging.
