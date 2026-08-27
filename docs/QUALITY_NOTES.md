# DubLocal quality notes

This document records the quality policy behind `v0.5.0.dev0`. “AI quality” is not one problem: source recognition, timing, context, translation fluency, TTS pronunciation, timing fit and final media handling can fail independently.

## Quality hierarchy

DubLocal treats the pipeline in this order:

```text
audio/source media
  → source subtitle accuracy
  → stable timing/IDs
  → hardware-appropriate contextual translation
  → optional context-aware review
  → structural/output validation
  → speech-only TTS preparation
  → voice generation
  → timing fit
  → soundtrack mix
  → stream-copy/remux export
```

A later stage must not pretend it can reliably repair an unknown introduced earlier. Translation context is not permission to invent what an automatic captioner probably misheard; M5 mixing is not permission to claim dialogue separation that was never performed.

## Source subtitle quality

Creator/embedded text subtitles are preserved as supplied.

YouTube automatic captions are explicitly marked as automatic. When wording is clearly damaged, the recommended path is local Whisper transcription—especially Accurate Large-v3-Turbo-Q5 for songs, accents or noisy material—rather than asking the translator to hallucinate the missing original wording.

Whisper Auto detect is propagated into translation only when DubLocal can normalize a concrete returned language. If no usable language is supplied, the app asks for an explicit source language rather than guessing.

## Hardware-aware translation policy

DubLocal does not recommend the same contextual model to every Mac.

Current policy:

| Mac class | Recommended model | Review | Effective input-context cap |
| --- | --- | --- | ---: |
| Apple Silicon below 12 GB | Qwen3 4B Q4_K_M | off | 8,192 |
| Apple Silicon 12–23 GB | Qwen3 8B Q4_K_M | off | 16,384 |
| Apple Silicon 24 GB+ | Qwen3 8B Q4_K_M | on | 24,576 |
| Intel below 24 GB | Qwen3 4B Q4_K_M | off | 6,144 |
| Intel 24 GB+ | Qwen3 8B Q4_K_M | off | 12,288 |

These are cautious defaults, not hard compatibility claims. The actual llama.cpp runtime context allocation scales with the profile as well as the prompt budget so low-memory Macs are not forced to reserve a large KV cache unnecessarily.

## Context and translation semantics

Context grows with programme duration up to the hardware profile's ceiling. It combines programme-wide samples, nearby source dialogue and recent accepted translations.

Short media uses larger target chunks so a song or short clip can normally be understood as one coherent local section rather than many disconnected calls.

v0.5 explicitly asks the contextual model to use discourse context for:

- grammatical gender where the source establishes it;
- speaker/addressee/pronoun/reference continuity;
- recurring names/entities;
- idioms and phraseological expressions by meaning/register rather than literal word substitution;
- metaphors and figurative imagery without inventing new imagery;
- slang and profanity at the source register.

When the source is ambiguous, the prompt tells the model not to fabricate unsupported gender or reference merely to make the target language more specific.

On hardware profiles that enable it, the second review pass checks the same categories again against source + context + first-pass draft.

## Protected subtitle cues

Closed-caption cues are useful subtitle information but are not dialogue.

Standalone tags such as `[MUSIC]`, `[APPLAUSE]` and `[LAUGHTER]` bypass translation and remain unchanged in SRT/VTT output.

For TTS, `voice_text.py` creates a temporary speech-only timeline. Bracketed cues are removed only from that temporary input. The user's subtitle file is never rewritten merely to make Kokoro silent on cues.

This means:

```text
[MUSIC]            stays in subtitles; not spoken
[LAUGHS] Hello     stays in subtitles; Kokoro speaks “Hello”
```

## Translation validation policy

Automated validation is intentionally conservative. It can prove alignment and reject obvious contamination; it cannot prove that a translation is elegant.

Before writing translated SRT, DubLocal verifies:

- subtitle IDs/order/timestamps remain aligned;
- no llama.cpp runtime/log/prompt content leaked into text;
- unexpected non-target script contamination is rejected;
- substantial wrong-script leakage is rejected;
- protected tags remain untouched.

If contextual recovery cannot produce validated output, DubLocal stops instead of creating a plausible-looking corrupt file.

## TTS quality boundary

Kokoro voice generation is separate from translation support. A language can have good subtitles even when the official Kokoro frontend does not support it.

DubLocal does not silently choose a mismatched pronunciation frontend merely to produce audio.

## M5 timing quality

The first timing engine prioritizes intelligibility over rigid timestamp compliance.

For overflowing speech it:

1. borrows available silence until the next spoken segment;
2. applies a modest FFmpeg tempo increase only if needed;
3. caps that speed-up at 1.25×;
4. never deliberately truncates words;
5. reports residual overflows that still cannot fit.

Future semantic shortening/rephrasing can improve difficult dubbing cases, but v0.5 does not hide destructive truncation behind a successful status.

## M5 audio quality boundary

The default dubbed soundtrack uses sidechain ducking of the source's primary audio plus an overlay of the generated voice.

This preserves underlying ambience/music/effects better than replacing the whole soundtrack with dry TTS, but it is **not source separation**. Original dialogue may remain quietly audible.

DubLocal therefore avoids claims such as “dialogue replacement” unless true dialogue/background separation is implemented later.

## Video integrity policy

M5 treats video and audio processing independently.

Where the requested container accepts the original video stream, DubLocal uses FFmpeg stream-copy (`-c:v copy`). This avoids generation loss and unnecessary processing time.

The new dubbed soundtrack must be audio-encoded because it is newly mixed. That does not justify re-encoding the video.

If MP4 cannot carry the selected source streams by remuxing, DubLocal directs the user to MKV instead of silently starting a video transcode.

## Human quality boundary

Neither Qwen3 4B/8B nor the current Kokoro/M5 pipeline is represented as equivalent to professional human translation, voice acting or studio dubbing.

The side-by-side Original/Translation preview remains important because semantic nuance, humour, lyric interpretation, cultural adaptation, casting and final mix aesthetics are not fully machine-verifiable.

Quality regressions should be reported with the smallest lawful sample that reproduces the problem and enough neighboring context to establish the intended meaning.
