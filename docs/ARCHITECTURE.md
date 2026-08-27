# DubLocal architecture

**Current development build: v0.5.1.dev0 — Voice Match + Export Refinement**

DubLocal is a local-first media pipeline made from separable stages. The Gradio UI coordinates jobs, but source inspection, transcription, translation, TTS, timing, mixing and remuxing remain independent modules with explicit failure boundaries.

## Pipeline

```text
YouTube / local media
        ↓
inspection + caption discovery
        ↓
existing text subtitles OR local whisper.cpp transcription
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
M4 / v0.5.1 Kokoro TTS
  ├─ manual voice OR automatic vocal-range matching
  ├─ one Kokoro pipeline/model
  ├─ per-segment voice preset selection
  ├─ per-segment WAVs
  └─ synchronized voice-only WAV + manifest
        ↓
M5 timing fit
  ├─ borrow silence before next spoken segment
  └─ modest atempo speed-up, capped at 1.25×
        ↓
M5.1 soundtrack mix
  ├─ source subtitle windows drive strong original-dialogue suppression
  ├─ fitted voice remains the audible sidechain reference
  └─ voice overlaid into AAC dubbed mix
        ↓
M5.1 remux/export
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
6. Heavy models download only after explicit user action.
7. Reuse system executables, shared model caches and compatible external runtimes before installing duplicates.
8. Never merge Python virtual environments or inject another application's `site-packages` into DubLocal.
9. No silent cloud fallback and no silent downgrade from contextual translation to OPUS.
10. Translation must pass alignment/runtime-leakage/target-script validation before SRT output.
11. One failed backend must not invalidate simpler completed stages.
12. Video re-encoding is never implied merely by audio/subtitle changes.
13. Local-file export defaults to stream-copy. Re-encoding occurs only after an explicit lower-resolution selection.
14. Automatic voice matching must stay lightweight: no extra TTS model, diarization model or source-separation model is required.
15. Acoustic voice matching is preset selection, not speaker identity or gender-identity classification.

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

## Transcription

`transcription.py` manages `whisper-cli`, FFmpeg speech preparation and optional Whisper weights. Base is the normal default; Large-v3-Turbo-Q5 is the optional higher-accuracy path for songs, accents, noisy material or damaged automatic captions.

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

## TTS preparation

`voice_text.py` creates a temporary speech-only SRT. `[MUSIC]` becomes silence; `[LAUGHS] Hello` becomes spoken `Hello`. The original subtitle file is unchanged.

`tts.py` and `kokoro_worker.py` generate per-segment WAVs, a synchronized voice-only WAV and `voice-manifest.json`. Compatible external Kokoro environments are invoked through their own Python process; they are never imported into DubLocal's interpreter.

## Automatic vocal-range matching

`voice_match.py` is the v0.5.1 lightweight casting layer.

It:

1. decodes the original primary audio to a temporary low-rate mono WAV;
2. examines audio inside source subtitle windows;
3. estimates dominant fundamental frequency with a NumPy autocorrelation path;
4. classifies usable segments into lower/higher vocal-range buckets;
5. maps those buckets to available Kokoro lower/higher presets for the selected language;
6. stores the selected voice per segment in the Kokoro manifest.

The matcher does not load another ML model. `kokoro_worker.py` keeps one KPipeline and changes `voice=` per request segment, so mixed two-range material does not double model memory.

If analysis is inconclusive, no source media is available, or a language exposes only one usable voice, the normal Kokoro default is used.

## Timing fit

M5 reads the Kokoro manifest. For overflowing lines it first extends into real silence up to the next spoken segment, then uses FFmpeg `atempo` up to 1.25×. Speech is never deliberately truncated; residual overflow is reported.

## Stronger dialogue/singing suppression

Professional dubbing ideally uses a dialogue-free Music & Effects stem. Ordinary consumer media often provides only a married mix, so `m5.py` cannot perfectly isolate original dialogue without source separation.

v0.5.1 improves the fallback using the **source subtitle timeline**:

- subtitle windows are converted into a timeline gain envelope;
- nearby windows are merged to reduce pumping;
- original audio is strongly attenuated across the full source dialogue/singing window, not merely while synthesized TTS is non-silent;
- sidechain compression remains as a secondary protection around the generated voice;
- when no usable source timeline exists, DubLocal falls back to stronger voice-driven ducking.

This is intentionally described as suppression/ducking, not source separation.

## Subtitle muxing

`subtitle_mux.py` prepares generated subtitle tracks for final media packaging.

By default, when available:

- generated original/source subtitles are embedded;
- generated translated subtitles are embedded;
- they remain selectable and are never burned into the image.

MKV preserves existing source subtitle streams and adds DubLocal tracks. MP4 maps generated subtitle tracks as `mov_text`. Track language/title/default metadata is set independently from audio metadata.

## Video quality policy

`video_quality.py` defines:

```text
Original / best available
2160p maximum
1440p maximum
1080p maximum
720p maximum
480p maximum
```

For YouTube, the selected value controls yt-dlp format selection before source acquisition; the chosen video is stream-copied during final remux.

For local media, Original means `-c:v copy`. A lower explicit quality creates a separate prepared source with FFmpeg H.264 VideoToolbox. DubLocal never silently downscales and never upscales a source just because a higher limit is selected.

## Export modes

**Replace primary audio — default**: the DubLocal mix becomes primary/default audio; additional original audio streams are retained where possible.

**Add dubbed audio as second track**: original audio streams remain untouched and DubLocal is appended as another selectable track.

MKV remains the recommended container. MP4 is used only when requested streams can be packaged compatibly. Audio processing/re-encoding of the new mix does not imply video re-encoding.

## UI layering

`ui.py` remains the stable earlier workflow implementation. `ui_v042.py` adds hardware-adaptive translation policy. `ui_v050.py` adds reliable language propagation, readable filenames, speech-only TTS preparation and the Export stage. `ui_v051.py` extends that working layer with automatic voice matching, subtitle mux defaults and export-quality controls rather than replacing the Main design.

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

Temporary YouTube downloads, voice-analysis audio, fitted voice, subtitle conversion, dubbed mixes and remux outputs are covered by the same lifecycle. Persistent model assets/shared Hugging Face cache are outside it.

## Still out of scope

- OCR for image subtitle streams;
- full speaker diarization/identity tracking;
- professional dialogue/M&E source separation;
- semantic rephrasing specifically to fit difficult dub timing;
- signed/notarized macOS packaging.
