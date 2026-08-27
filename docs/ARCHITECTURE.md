# DubLocal architecture

**Current development build: v0.4.2.dev0 — Subtitle Export + Translation Quality Pass**

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
        ├──────────────→ SRT / VTT / TXT export
        ↓ optional
translation
  ├─ Recommended for this Mac
  │    ├─ Qwen3 4B lightweight
  │    └─ Qwen3 8B balanced / best + optional review
  └─ Fast legacy · OPUS/Marian                    ← explicit minimum-storage choice
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
2. Subtitles are a first-class output; translation and voice generation are optional downstream stages.
3. The default contextual path must use dialogue context and must not translate subtitle rows as unrelated sentences.
4. Hardware recommendation must account for architecture, physical/unified memory, runtime context allocation and practical inference time.
5. Longer programmes receive a larger context budget only up to the active hardware profile's ceiling.
6. Standalone caption tags are structural data and bypass translation.
7. Optional heavy models are downloaded only after explicit user action.
8. Reuse existing executables, shared model caches and compatible external runtimes before installing duplicates.
9. Never merge Python virtual environments or inject another application's `site-packages` into DubLocal.
10. No silent cloud fallback and no silent downgrade from the selected contextual profile to OPUS.
11. Model registrations require explicit licence, immutable revision and checksum metadata.
12. Generated translation must pass alignment, runtime-leakage and target-script validation before an SRT is written.
13. A backend failure must not disable simpler stages such as caption extraction/transcription/export.
14. Adding/replacing audio must not imply video re-encoding; M5 prefers stream-copy.

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

`src/dublocal/subtitle_export.py` converts that stable timeline to user-facing SRT, WebVTT or TXT without re-running transcription.

## M2 transcription + v0.4.2 accurate option

`src/dublocal/transcription.py` manages local `whisper-cli`, FFmpeg speech preparation and optional model weights.

Base remains the default general-purpose model. v0.4.2 adds Large-v3-Turbo-Q5 as an optional higher-accuracy source path for songs, accents and noisy material. The UI explicitly distinguishes automatic YouTube captions from creator/embedded subtitles because translation must not be treated as an ASR-repair engine.

## M3 legacy translation

`src/dublocal/translation.py` remains the lightweight legacy backend using pinned Helsinki-NLP OPUS/Marian safetensors models.

It is retained because it is small and fast. Its sentence-level architecture is deliberately not the default contextual path.

## v0.4.2 adaptive contextual translation

The contextual path is split so hardware policy, model/storage policy, runtime lifetime, prompt policy and validation remain independently testable:

```text
hardware_profile.py            Mac architecture/RAM detection + recommendation tier
adaptive_contextual.py         choose/register Qwen3 4B or Qwen3 8B for that tier
contextual_translation.py      pinned Qwen3 4B model + shared context primitives
contextual_quality_model.py    pinned Qwen3 8B model registration/download
contextual_runtime.py          one adaptive llama-server session per job
contextual_policy.py           context/chunk planning + translation/review prompts
contextual_progress.py         orchestration, hardware cap, recovery, review, SRT writing
translation_quality.py         protected tags + target-output validation
contextual_recovery.py         strict ID-oriented recovery
```

### Hardware recommendation

`hardware_profile.py` reads local architecture and physical memory. The current conservative defaults are:

```text
Apple Silicon < 12 GB     Qwen3 4B · review off · 8,192 input cap
Apple Silicon 12–23 GB    Qwen3 8B · review off · 16,384 input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · 24,576 input cap
Intel < 24 GB             Qwen3 4B · review off · 6,144 input cap
Intel 24 GB+              Qwen3 8B · review off · 12,288 input cap
```

These are recommendations, not hard support declarations. The purpose is to prevent the “strongest available model” from becoming a poor product default on low-memory or CPU-bound Macs.

The primary Main UI receives only the resulting label: **Recommended for this Mac · Lightweight / Balanced / Best quality**. Detailed reasoning stays in the collapsed engine details and Model Manager.

### Context allocation versus prompt budget

There are two separate limits:

1. **Input budget** — how much source/context material DubLocal puts into the prompt.
2. **llama.cpp runtime context** — how much KV/context capacity llama.cpp allocates.

Both are hardware-scaled. The runtime allocation is currently the profile's input cap plus output/instruction headroom, capped by the model's native context. This is essential on an 8 GB M1: sending an 8k prompt while still launching `llama-server -c 32768` would leave much of the memory problem intact.

### Contextual models

```text
Qwen/Qwen3-4B-GGUF
Qwen3-4B-Q4_K_M.gguf
~2.5 GB
Apache-2.0

Qwen/Qwen3-8B-GGUF
Qwen3-8B-Q4_K_M.gguf
~5.03 GB
Apache-2.0
```

Both models use the normal shared Hugging Face cache and separate DubLocal registrations. Registration requires the exact configured upstream revision and checksum.

`Prepare / verify contextual translation` downloads only the model recommended for the current Mac. It does not install both merely because both are supported.

### Runtime lifetime

The preferred path is a loopback-only `llama-server` bound to `127.0.0.1` on an ephemeral port.

One server/model load is reused for:

- every translation chunk;
- structured/plain-text recovery;
- missing-ID recovery;
- the optional senior-review pass.

This solves two earlier architectural problems: repeated model startup on short jobs and accidental mixing of CLI runtime output with generated subtitle text.

A sanitized `llama-cli --simple-io` path remains only for compatibility when `llama-server` is unavailable.

Server logs are written under the temporary DubLocal jobs cache and are covered by the normal 24-hour/4-GiB pruning policy.

### Context planning

Before hardware capping, the source-context planner is duration-aware:

```text
base input context       4,096 tokens
additional context       +128 tokens per programme minute
absolute input ceiling  24,576 tokens
model native context    32,768 tokens
```

The active hardware profile may impose a lower ceiling.

Target chunk size is deliberately larger for short media:

```text
≤ 10 min      48 subtitle segments
≤ 30 min      36
≤ 90 min      28
> 90 min      24
```

A short song therefore normally fits into one contextual chunk rather than several independent requests.

### Context layers

Each target chunk can receive:

1. **Programme-wide source context** — evenly sampled source lines for recurring names/topics/references.
2. **Nearby source context** — source lines before and after the target chunk.
3. **Recent translated context** — prior accepted translations as terminology/style memory.

The prompt also tells the model to read subtitle fragments as continuous speech when a sentence crosses timestamp boundaries.

### Target-language rules

`translation_quality.py` supplies target-language guidance. For Russian, for example, the prompt explicitly requires idiomatic contemporary Russian, natural case/gender/number/aspect, no English-syntax calques, no pseudo-Russian transliterations and no ordinary untranslated English words.

These rules are semantic guidance, not a claim that grammar can be perfectly validated by regex.

### Best-quality review pass

Only the hardware profiles that enable review run it automatically. The first translation draft is already alignment/script/runtime validated. Best quality then asks the same loaded Qwen3 8B model to perform a second senior-review pass against:

- the original target source lines;
- the complete contextual prompt;
- the first-pass draft.

The review focuses on mistranslation, calques, target-language grammar, word choice, untranslated ordinary words, recurring terminology and register/profanity consistency.

Because the same model stays loaded, the review mainly increases inference time rather than allocating a second model-sized block of memory.

If the review response is structurally invalid, DubLocal keeps the already-valid draft. Review cannot corrupt a usable result.

### Protected caption tags

Standalone bracketed cues such as `[MUSIC]`, `[APPLAUSE]` and `[LAUGHTER]` never enter the translation model. They are copied exactly into the output timeline.

### Output validation

Before any translated text becomes SRT:

- runtime banners/model paths/prompts/control characters are rejected;
- CJK/Hangul contamination is rejected for the current European target set;
- Cyrillic targets reject substantial Latin-script leakage;
- Latin targets reject substantial Cyrillic leakage;
- every target subtitle ID must be present exactly once;
- unexpected IDs are rejected;
- ordering/timestamps are reconstructed from the source timeline, never from model output.

Recovery receives the original context. If output still cannot be validated, the translation stops instead of writing a corrupted SRT.

### Source-quality boundary

Contextual translation is not an audio decoder. If an automatic-caption source already contains incorrect words, DubLocal does not instruct Qwen to hallucinate the probable original lyrics/dialogue.

The intended repair path is upstream:

```text
bad automatic captions
        ↓
local Accurate Whisper transcription from audio
        ↓
better source timeline
        ↓
contextual translation
```

## Dependency reuse

`src/dublocal/dependencies.py` reports/reuses:

- FFmpeg and ffprobe;
- `whisper-cli`;
- `llama.cpp` executables;
- shared Hugging Face cache;
- compatible external Python environments.

### Python environment boundary

On macOS, separate venv `bin/python` paths may point to the same underlying framework binary. DubLocal preserves the virtual-environment entry-point identity rather than resolving that symlink away.

Supported external Python backends run a dedicated worker process with that environment's own interpreter; no cross-venv import-path manipulation occurs.

## M4 Kokoro voice generation

`src/dublocal/tts.py` and `src/dublocal/kokoro_worker.py` generate a local voice-only timeline.

The worker can run inside a compatible external Kokoro environment. It writes per-segment WAV assets and metadata into DubLocal's job directory. `tts.py` assembles the voice timeline at original subtitle start times and reports timing overflow data for M5.

Kokoro and translation are separate capabilities. A language can be translated successfully even when Kokoro has no official voice frontend for it.

## Main / Settings split

The v0.4 UI keeps ordinary processing under **Main** and maintenance under **Settings**.

Settings contains:

- **Updates**;
- **Model Manager** — Whisper, adaptive contextual translation, Fast legacy OPUS, Kokoro;
- **Local Resources**.

Model install/remove controls stay out of the normal processing flow.

`ui_v042.py` is a deliberately small transition adapter binding the stable v0.4 layout to the adaptive translation policy while the larger `ui.py` is awaiting its next structural refactor. It avoids copying the entire Gradio layout solely to swap model policy.

## Updates and repair

`src/dublocal/updater.py` distinguishes the running package, local Git checkout and official `origin/main`.

Normal updates require a clean fast-forward. Repair is a separate explicit operation that can back up modified tracked files, restore official source and refresh the managed Python core while preserving models/caches/jobs/untracked files.

## Temporary job lifecycle

`src/dublocal/job_cache.py` owns generated/intermediate job cleanup.

Default policy:

```text
root       ~/Library/Caches/DubLocal/jobs/
max age    24 hours
max size   4 GiB
strategy   age first, then oldest-first size pruning
```

Persistent models/shared HF cache are explicitly outside this lifecycle.

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
