# DubLocal architecture

**Current development build: v0.5.3.dev0 — M5 Stabilization**

DubLocal is a local-first pipeline with explicit stage boundaries. The Gradio UI coordinates jobs, but source inspection, transcription, translation, TTS, timing, mixing and remuxing remain separable.

## Pipeline

```text
YouTube / local media
        ↓
inspection + caption discovery
        ↓
existing subtitles OR local whisper.cpp transcription
  ├─ conservative anti-ghost policy
  └─ v0.5.3 targeted two-pass sparse/gap recovery
        ↓
normalized Segment[] timeline
        ├──────────────→ SRT / VTT / TXT
        ├──────────────→ original media + source subtitles only
        ↓ optional
contextual translation
  ├─ hardware-aware Qwen3 4B / 8B
  └─ optional legacy OPUS
        ↓ optional
speech-only TTS preparation
        ↓
Kokoro
  ├─ one local pipeline/model
  ├─ manual or automatic lower/higher vocal-range preset
  └─ per-segment WAV + manifest
        ↓
v0.5.3 timing fit
  ├─ subtitle-window target
  ├─ chained atempo, effective 0.30×–2.50×
  └─ small end-time correction pass
        ↓
v0.5.3 soundtrack mix
  ├─ stable reduced original bed
  ├─ deeper subtitle-window dialogue/singing attenuation
  └─ gentle compressor + limiter
        ↓
track-aware remux/export
  ├─ replace primary audio
  ├─ add dubbed audio
  ├─ package original + source subtitles only
  ├─ selectable subtitle tracks
  └─ video stream-copy unless explicitly downscaled
```

## Core design rules

1. Subtitle IDs/timestamps are stable data; translation/TTS do not rewrite them.
2. Subtitles are a complete output. Every downstream stage is optional.
3. One failed stage must not invalidate a simpler completed stage.
4. Caption cues remain subtitle data but are not translated as dialogue and are not spoken.
5. Hardware recommendations scale both translation model and llama.cpp KV/context allocation.
6. Heavy models download only after user action; reusable executables/caches/runtimes are preferred.
7. Python virtual environments are never merged.
8. No silent cloud fallback and no silent contextual→OPUS downgrade.
9. Video re-encoding is never implied by audio/subtitle changes.
10. M1/low-memory compatibility is a runtime design constraint, not an afterthought.
11. ASR recovery must prefer uncertainty/gaps over invented speech.
12. DubLocal does not claim source separation when it is only attenuating a married mix.

## Subtitle timeline

`timeline.py` uses integer milliseconds:

```text
Segment
  index: int
  start_ms: int
  end_ms: int
  text: str
```

`subtitle_export.py` creates SRT/VTT/TXT from that timeline. `output_naming.py` exposes source-derived filenames while internal jobs remain disposable.

## Transcription reliability

`transcription.py` is the base whisper.cpp integration. `transcription_guard.py` protects against severe repetition/hallucination loops. `transcription_v053.py` adds selective missing-word recovery.

The policy is intentionally asymmetric:

- ordinary speech may use Silero VAD when supported;
- Accurate music transcription disables rolling text context that can self-reinforce a false lyric;
- pathological near-duplicate runs are isolated and retried;
- severe persistent loops are suppressed rather than sent to translation/TTS;
- v0.5.3 identifies only a small number of suspicious sparse regions/gaps;
- each proposed recovery is decoded twice independently with no context;
- both passes must agree closely;
- neighbour-echo candidates are rejected.

Low-memory Apple Silicon is capped at 3 recovery regions / 24 seconds. There is no second full-file pass and no extra ASR model.

## Adaptive contextual translation

Relevant modules:

```text
hardware_profile.py          architecture/RAM detection
adaptive_contextual.py       recommended model/profile
contextual_runtime.py        llama-server / llama-cli lifetime
contextual_policy.py         context + translation/review prompts
contextual_progress.py       orchestration + Auto source-language ID
translation_quality.py       output validation
contextual_recovery.py       strict subtitle-ID recovery
```

Current defaults:

```text
Apple Silicon <12 GB      Qwen3 4B · 8,192 input cap
Apple Silicon 12–23 GB    Qwen3 8B · 16,384 input cap
Apple Silicon 24 GB+      Qwen3 8B · review · 24,576 cap
Intel <24 GB              Qwen3 4B · 6,144 cap
Intel 24 GB+              Qwen3 8B · 12,288 cap
```

`From = Auto` can use the same already-loaded Qwen runtime to identify the dominant subtitle language before contextual translation. Translation prompts cover discourse reference/gender where supported, idioms/phraseology, metaphors, terminology continuity, slang/profanity and recurring refrains.

## TTS and voice matching

`voice_text.py` creates a temporary speech-only SRT. `tts.py`/`kokoro_worker.py` generate per-segment audio and `voice-manifest.json`.

`voice_match.py` performs lightweight F0/range analysis on the source and chooses lower/higher Kokoro presets by segment. One Kokoro model/pipeline remains loaded; this is not diarization, speaker identity or gender-identity inference.

## v0.5.3 timing

`m53.py` installs the current timing fitter behind the stable M5 API.

For each generated segment:

1. read subtitle start/end and generated WAV duration;
2. reserve a small onset cushion;
3. calculate the factor required to occupy the target window;
4. construct a legal chain of FFmpeg `atempo` filters (each stage 0.5–2.0) for an effective 0.30–2.50 range;
5. measure the result;
6. apply a small correction pass when rounding leaves more than roughly 25 ms mismatch;
7. assemble at the original subtitle-relative start.

Pathological factors remain reported rather than forced. SRT timing is never modified.

## v0.5.3 soundtrack balance

`m53.py` also replaces the previous mix behavior behind the existing export API.

The original programme is held at a stable reduced bed level. Source subtitle dialogue/singing windows receive deeper attenuation. The generated voice remains foreground. A gentle compressor and limiter keep the final programme from jumping abruptly in perceived loudness between dubbed and non-dubbed sections.

This is DSP on a married soundtrack, not dialogue/M&E source separation.

## Export

`m51.py` owns quality-aware source acquisition and track-aware remuxing. `m53.py` adds subtitle-only packaging.

Modes:

- Replace primary audio;
- Add dubbed audio as another track;
- **Package original + subtitles · no dub**.

Normal dubbed exports embed generated original + translated subtitles when available. Subtitle-only packaging embeds the current source/transcribed subtitle and leaves audio untouched.

For local sources, Original video quality uses `-c:v copy`; lower resolution is an explicit VideoToolbox transcode. For YouTube, quality is selected before download and the chosen video is then stream-copied.

## UI layering

The product intentionally preserves a stable normal workflow while behavior evolves behind adapters:

```text
ui.py          base workflow
ui_v042.py     hardware-aware contextual translation
ui_v050.py     M5 workflow / voice / export adapters
ui_v053.py     v0.5.3 export mode/status refinements
```

Main remains:

```text
1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export
```

Settings remains:

```text
Updates | Model Manager | Local Resources
```

## Temporary jobs

`job_cache.py` owns disposable job data:

```text
~/Library/Caches/DubLocal/jobs/
max age: 24 h
max size: 4 GiB
```

Temporary downloads, analysis audio, transcription WAVs, subtitles, llama logs, TTS segments, fitted audio, mixes and remux outputs are covered. Persistent models/shared Hugging Face cache are outside this lifecycle.

## Still out of scope

- OCR for image subtitle tracks;
- full speaker diarization/identity tracking;
- professional M&E/dialogue source separation;
- semantic rewriting specifically to avoid extreme timing factors;
- signed/notarized macOS packaging.
