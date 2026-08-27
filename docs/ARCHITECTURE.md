# DubLocal architecture

**Current development build: v0.4.1.dev0 / M4 + M3.1 Contextual Translation**

DubLocal is a local pipeline of replaceable stages. The Gradio UI coordinates jobs; media inspection, transcription, translation, TTS and later rendering remain separate modules with separate dependencies and failure boundaries.

## Pipeline

```text
YouTube / local media
        ↓
inspection + caption discovery
        ↓
existing text subtitles OR local whisper.cpp transcription
        ↓
normalized Segment[] timeline (stable IDs + integer millisecond timing)
        ↓
translation (optional)
  ├─ Contextual quality · Qwen3 4B + llama.cpp   ← default
  └─ Fast legacy · OPUS/Marian                  ← explicit fallback choice
        ↓
source or translated SRT
        ↓
M4 Kokoro TTS
  ├─ reusable isolated Python runtime
  ├─ per-segment WAVs
  └─ synchronized voice-only WAV + manifest
        ↓
M5 duration fitting + original-audio mix
        ↓
stream-copy/remux video where compatible
```

## Design rules

1. Subtitle IDs and timestamps are stable data. Translation changes text, not timing.
2. The default translation path must use dialogue context; it must not translate subtitle rows as unrelated sentences.
3. Longer programmes receive a larger translation-context budget, bounded by the local model's context window.
4. Optional heavy models are downloaded only after an explicit user action.
5. Reuse existing executables, shared model caches and compatible external runtimes before installing duplicates.
6. Never merge Python virtual environments or inject another application's `site-packages` into DubLocal.
7. No silent cloud fallback and no silent downgrade from the selected quality backend.
8. Model registrations require explicit licence, immutable revision and checksum metadata.
9. A backend failure should not disable simpler stages such as caption extraction or SRT export.
10. Adding/replacing audio must not imply video re-encoding; M5 prefers stream-copy.

## Normalized timeline

`src/dublocal/timeline.py` defines:

```text
Segment
  index: int
  start_ms: int
  end_ms: int
  text: str
```

Integer milliseconds avoid accumulated timing drift. Extracted captions and Whisper transcription are normalized to this structure/SRT before later stages.

## M2 transcription

`src/dublocal/transcription.py` manages local `whisper-cli`, FFmpeg speech preparation and Tiny/Base/Small Whisper models. Whisper can hand its detected language into the translation UI.

## M3 legacy translation

`src/dublocal/translation.py` remains the lightweight legacy translation engine using pinned Helsinki-NLP OPUS/Marian safetensors models.

It is intentionally retained because it is small and fast, but its sentence-level design is no longer the default quality path.

## M3.1 contextual translation

`src/dublocal/contextual_translation.py` is the default translation backend in v0.4.1.dev0.

### Runtime and model

```text
llama.cpp
  +
Qwen/Qwen3-4B-GGUF
Qwen3-4B-Q4_K_M.gguf
```

DubLocal looks for `llama-cli`/`llama cli` first. If absent, Model Manager can install `llama.cpp` through Homebrew. The GGUF is stored in the normal shared Hugging Face cache, linked into DubLocal's model registration, pinned to an immutable upstream revision and SHA-256 verified before use.

### Context planning

A translation request is not one subtitle row at a time. DubLocal creates a `ContextPlan` from the programme duration.

Current policy:

```text
minimum input context    4,096 tokens
additional context       +128 tokens per programme minute
maximum input context   24,576 tokens
Qwen native context     32,768 tokens
```

The ceiling intentionally leaves space for system/user instructions and generated subtitle JSON.

Longer programmes also use slightly larger target chunks (bounded at 20 subtitle segments) to reduce repeated model startup while keeping output alignment easy to verify.

### Three context layers

Each target chunk receives:

1. **Programme-wide source context** — evenly sampled lines from across the media, useful for recurring names/topics and later callbacks.
2. **Nearby source context** — lines immediately before and after the target chunk, weighted more heavily toward preceding dialogue.
3. **Recent translated context** — prior accepted/generated translations, carried forward as terminology and style memory.

This structure lets the translator reason about pronouns, speaker intent, slang, jokes, profanity/register and recurring terminology while still preserving one output item per original subtitle ID.

### Alignment contract

The model is instructed through its chat template with reasoning disabled for this deterministic transformation task. `llama.cpp` is given a JSON schema so output must be an array of:

```json
{"id": 123, "text": "translated subtitle"}
```

DubLocal validates that every requested ID occurs exactly once and that no unexpected ID appears. If alignment fails, the job stops instead of producing a shifted SRT.

### No hidden fallback

If Qwen/llama.cpp is not prepared or fails, Contextual quality reports the error. It does not silently invoke OPUS or a cloud API. The user can explicitly choose **Fast legacy · OPUS** when desired.

## Dependency reuse

`src/dublocal/dependencies.py` reports/reuses:

- FFmpeg and ffprobe;
- `whisper-cli`;
- `llama.cpp` / `llama-cli`;
- the shared Hugging Face cache;
- compatible external Python environments.

### Python environment boundary

On macOS, separate venv `bin/python` paths may point to the same underlying framework binary. DubLocal preserves the venv entry-point identity rather than resolving the symlink. This is how a separate Kokoro environment can be reused safely while remaining isolated.

Supported external Python backends run a dedicated worker process with that environment's own interpreter; no cross-venv import path manipulation occurs.

## M4 Kokoro voice generation

`src/dublocal/tts.py` and `src/dublocal/kokoro_worker.py` generate a local voice-only timeline.

The worker can run inside a compatible external Kokoro environment. It writes 24 kHz mono segment WAVs plus metadata into DubLocal's job directory. `tts.py` assembles them at the original subtitle start times and reports `voice_duration_ms`, `slot_ms` and `overflow_ms` for M5.

Kokoro and translation are separate capabilities. A language can be translated successfully even when Kokoro has no official voice frontend for it.

## Main / Settings split

`src/dublocal/ui.py` keeps ordinary processing under **Main** and maintenance under **Settings**.

Settings contains:

- **Updates**;
- **Model Manager** — Whisper, Contextual translation, Fast legacy OPUS, Kokoro;
- **Local Resources**.

Model installation/removal is not mixed into the ordinary job flow.

## Updates and repair

`src/dublocal/updater.py` distinguishes the running package, local Git checkout and official `origin/main`.

Normal updates require a clean fast-forward. Repair is a separate explicit operation that can back up modified tracked files, restore official source and refresh the managed Python core while preserving models/caches/jobs/untracked files.

## M5 boundary

M5 starts from the translated timeline and M4 voice manifest and adds:

- speech-duration fitting;
- original-audio ducking/mixing;
- default **Replace primary audio** mode;
- optional **Add dubbed audio as second track** mode;
- language/title/disposition metadata;
- `-c:v copy` whenever source video/container compatibility allows it.

True dialogue/background source separation remains a separate future feature and must not be implied by ordinary ducking/overlay.

## Still out of scope

- OCR for image subtitle streams;
- speaker diarization / automatic multi-voice casting;
- dialogue/background source separation;
- automatic duration fitting and soundtrack mix (M5);
- signed/notarized macOS packaging.
