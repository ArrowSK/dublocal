# DubLocal quality notes

This document records the quality policy behind `v0.5.2.dev0`. “AI quality” is not one problem: source recognition, timing, context, translation fluency, TTS pronunciation, timing fit and final media handling can fail independently.

## Quality hierarchy

DubLocal treats the pipeline in this order:

```text
audio/source media
  → speech/non-speech detection
  → source subtitle accuracy
  → stable timing/IDs
  → hardware-appropriate contextual translation
  → optional context-aware review
  → structural/output validation
  → speech-only TTS preparation
  → voice generation / vocal-range preset matching
  → per-line timing fit
  → soundtrack mix
  → track-aware stream-copy/remux export
```

A later stage must not pretend it can reliably repair an unknown introduced earlier. Translation context is not permission to invent what an automatic captioner probably misheard; audio mixing is not permission to claim dialogue separation that was never performed.

## Source subtitle quality and hallucination control

Creator/embedded text subtitles are preserved as supplied.

YouTube automatic captions are explicitly marked as automatic. When wording is clearly damaged, the recommended path is local Whisper transcription—especially Accurate Large-v3-Turbo-Q5 for songs, accents or noisy material—rather than asking the translator to hallucinate the missing original wording.

Whisper itself can hallucinate on silence, instrumental music or ambiguous non-speech. v0.5.2 therefore feature-detects whisper.cpp VAD support and, when available, uses the official Silero VAD v6.2.0 auxiliary speech detector. That reduces the amount of non-speech audio passed to Whisper. The auxiliary model is tiny, local, pinned/checksum-verified and not another transcription model.

Long-form transcription also caps carried text context at 64 tokens and uses a slightly stricter no-speech threshold. This reduces the risk that one mistaken phrase becomes self-reinforcing and repeats through later non-speech regions.

VAD does not make singing transcription infallible. It decides where speech/vocals are likely present; the selected Whisper model still decides what was said or sung.

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

The contextual model is explicitly asked to use discourse context for grammatical gender where established, speaker/addressee/pronoun/reference continuity, recurring names/entities, idioms and phraseological expressions by meaning/register, metaphor fidelity, slang/profanity and recurring refrains.

When the source is ambiguous, the prompt tells the model not to fabricate unsupported gender or reference merely to make the target language more specific.

On hardware profiles that enable it, the second review pass checks the same categories again against source + context + first-pass draft.

## Protected subtitle cues

Closed-caption cues are useful subtitle information but are not dialogue.

Standalone tags such as `[MUSIC]`, `[APPLAUSE]` and `[LAUGHTER]` bypass translation and remain unchanged in SRT/VTT output.

For TTS, `voice_text.py` creates a temporary speech-only timeline. Bracketed cues are removed only from that temporary input. The user's subtitle file is never rewritten merely to make Kokoro silent on cues.

```text
[MUSIC]            stays in subtitles; not spoken
[LAUGHS] Hello     stays in subtitles; Kokoro speaks “Hello”
```

## Translation validation policy

Automated validation is intentionally conservative. It can prove alignment and reject obvious contamination; it cannot prove that a translation is elegant.

Before writing translated SRT, DubLocal verifies subtitle IDs/order/timestamps remain aligned, no llama.cpp runtime/log/prompt content leaked into text, unexpected non-target script contamination is rejected, substantial wrong-script leakage is rejected and protected tags remain untouched.

If contextual recovery cannot produce validated output, DubLocal stops instead of creating a plausible-looking corrupt file.

## TTS and voice-matching quality boundary

Kokoro voice generation is separate from translation support. A language can have good subtitles even when the official Kokoro frontend does not support it. DubLocal does not silently choose a mismatched pronunciation frontend merely to produce audio.

Automatic voice matching is intentionally an acoustic lower/higher-range preset heuristic, not speaker recognition or gender-identity inference. It uses the existing source audio and one Kokoro pipeline; it does not add a diarization or second TTS model.

## v0.5.2 timing quality

The current timing engine targets the subtitle window rather than only correcting overflows.

For each generated segment it:

1. keeps the original subtitle start/end timestamps unchanged;
2. adds a small 35–100 ms onset cushion so synthetic speech does not consistently sound early;
3. treats the rest of the subtitle window as the target spoken duration;
4. derives the required FFmpeg `atempo` factor from actual generated WAV duration;
5. slows short lines or accelerates long lines;
6. constrains tempo to 0.5×–2.0×;
7. reports residual mismatch instead of forcing extreme, obviously degraded time stretching.

The practical target for normal lines is therefore to finish at approximately the same subtitle end time as the source. Extreme translation-length differences remain a semantic problem best solved later by rephrasing/shortening rather than unlimited audio distortion.

## Audio quality boundary

The default dubbed soundtrack uses subtitle-window-guided suppression of the source's primary audio plus an overlay of the generated voice.

This preserves underlying ambience/music/effects better than replacing the whole soundtrack with dry TTS, but it is **not source separation**. Original dialogue may remain faintly audible because ordinary consumer media usually contains a married mix rather than a dialogue-free Music & Effects stem.

DubLocal therefore avoids claims such as perfect “dialogue replacement” unless true dialogue/background separation is implemented later.

## Video and subtitle integrity policy

Audio, subtitle and video processing remain independent.

Where the requested output keeps original/local quality, DubLocal uses FFmpeg stream-copy (`-c:v copy`) whenever compatible. Selecting a lower local resolution is an explicit opt-in to VideoToolbox re-encoding; YouTube quality options select a source resolution before final remux.

Generated original and translated subtitles are packaged as selectable streams when available and are not burned into the picture by default.

The new dubbed soundtrack must be audio-encoded because it is newly mixed. That does not justify re-encoding the video.

## Human quality boundary

Neither Qwen3 4B/8B nor the current Kokoro/export pipeline is represented as equivalent to professional human translation, voice acting or studio dubbing.

The side-by-side Original/Translation preview remains important because semantic nuance, humour, lyric interpretation, cultural adaptation, casting and final mix aesthetics are not fully machine-verifiable.

Quality regressions should be reported with the smallest lawful sample that reproduces the problem and enough neighboring context to establish the intended meaning.
