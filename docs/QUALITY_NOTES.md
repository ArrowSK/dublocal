# DubLocal quality notes

This document records the quality policy behind `v0.5.3.dev0`. DubLocal treats recognition, translation, TTS, timing and mixing as separate quality layers; a later stage must not silently invent a fix for an unknown introduced earlier.

## Pipeline quality order

```text
source media
  → source/ASR subtitle accuracy
  → stable timing + IDs
  → contextual translation
  → output validation
  → speech-only TTS preparation
  → voice/range selection
  → per-line timing fit
  → soundtrack balance
  → track-aware remux
```

## Recognition: conservative first, targeted recovery second

YouTube automatic captions are not ground truth. For difficult audio the preferred source is local Whisper, especially Accurate Large-v3-Turbo-Q5 for songs/accents/noise.

Whisper can both hallucinate and omit words. v0.5.3 explicitly refuses the simplistic solution of globally lowering confidence/no-speech guards.

The policy is:

1. prevent self-reinforcing long-form loops (including no rolling context on the Accurate music path);
2. detect pathological near-duplicate storms;
3. independently re-decode suspicious ranges;
4. suppress a severe range if it still looks invented;
5. only then inspect a small number of sparse/gap regions for potentially missed speech;
6. accept missing-word recovery only if **two isolated no-context passes agree closely**;
7. reject neighbour echoes and weak/unrelated additions.

An uncertain gap is preferable to fabricated dialogue.

Low-memory Apple Silicon is capped at 3 extra regions / 24 seconds per transcription. No additional ASR model is loaded.

## Hardware-aware translation

| Mac class | Model | Review | Input cap |
| --- | --- | --- | ---: |
| Apple Silicon <12 GB | Qwen3 4B Q4_K_M | off | 8,192 |
| Apple Silicon 12–23 GB | Qwen3 8B Q4_K_M | off | 16,384 |
| Apple Silicon 24 GB+ | Qwen3 8B Q4_K_M | on | 24,576 |
| Intel <24 GB | Qwen3 4B Q4_K_M | off | 6,144 |
| Intel 24 GB+ | Qwen3 8B Q4_K_M | off | 12,288 |

The actual llama.cpp context allocation scales too. These are conservative defaults intended to keep an 8 GB M1 usable.

## Contextual translation semantics

Context combines programme-wide samples, nearby dialogue and recent accepted translations. The prompt/review explicitly handles:

- speaker/addressee/reference continuity;
- grammatical gender only when supported by context;
- recurring names/terminology;
- idioms and phraseology by meaning/register;
- metaphor/image fidelity without invented imagery;
- slang, profanity and recurring refrains.

`From = Auto` may use the same local Qwen runtime to identify the dominant subtitle language before contextual translation.

## Protected subtitle cues

Standalone cues such as `[MUSIC]`, `[APPLAUSE]` and `[LAUGHTER]` remain unchanged in subtitle output and bypass dialogue translation.

TTS uses a temporary speech-only timeline:

```text
[MUSIC]            subtitle kept; no speech
[LAUGHS] Hello     subtitle kept; speaks “Hello”
```

## Translation validation

Before writing the translated SRT, DubLocal verifies alignment/IDs/timestamps, rejects llama.cpp runtime/prompt leakage, rejects unexpected writing-system contamination and preserves protected tags. Validation can reject obvious corruption; it cannot prove literary quality.

## Voice matching boundary

Automatic voice matching is a lightweight acoustic lower/higher-range preset heuristic. It is not speaker identity, diarization or gender-identity inference. One Kokoro pipeline/model stays loaded; voice presets change per segment.

## v0.5.3 timing quality

Each generated segment targets its subtitle window. The engine:

1. preserves original SRT start/end timestamps;
2. applies a small onset cushion;
3. measures the generated WAV;
4. derives the required tempo;
5. chains legal FFmpeg `atempo` stages to cover an effective 0.30×–2.50× range;
6. measures the fitted output;
7. applies a small second correction when rounding leaves the spoken end >~25 ms from target;
8. reports pathological stretches rather than forcing them.

The goal is synchronized end timing, not unlimited time-stretching.

## v0.5.3 soundtrack balance

Professional dubbing normally uses a dialogue-free M&E stem. Consumer media usually does not provide one.

DubLocal therefore uses transparent terminology: **attenuation/ducking + overlay**, not source separation.

v0.5.3 keeps the source programme at a stable reduced bed level throughout a dubbed mix, attenuates it more deeply during source subtitle dialogue/singing windows, and applies gentle compression/limiting to prevent large perceived loudness jumps between dubbed and non-dubbed sections.

This is intentionally lightweight enough for M1-class hardware and does not add a separation model.

## Subtitle/video integrity

Normal dubbed export can embed generated source + translated subtitles as selectable tracks. **Package original + subtitles · no dub** embeds only the current source/transcribed subtitle and leaves original audio untouched.

Subtitles are not burned by default.

For local Original quality, video uses stream-copy. Explicit local downscaling is the only normal path that invokes VideoToolbox encoding. Audio mixing never justifies an unnecessary video transcode.

## Human quality boundary

DubLocal is not presented as equivalent to professional human translation, voice acting, lyric adaptation or studio dubbing. Side-by-side source/translation review remains important for nuance, humour, cultural adaptation, ambiguous lyrics and final mix aesthetics.

Quality regressions should be reported with the smallest lawful sample and enough neighbouring context to establish the intended result.
