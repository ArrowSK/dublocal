# DubLocal architecture

**Current development build: v0.6.0.dev0 — Magic Flow UX**

DubLocal is a local-first media pipeline with two user-facing control layers over the same processing engines:

- **Magic Flow** — compact orchestration and hardware-safe recommendations.
- **Detailed workflow** — explicit stage-by-stage control.

Magic Flow is not a second backend. It resolves dependencies and calls the same source, transcription, translation, TTS, timing, mixing and remuxing modules used by the detailed workflow.

## Product-level flow

```text
Magic Flow
  source + rights + output language + desired outputs
        ↓
route recommendation / dependency resolution
        ↓
existing DubLocal pipeline
```

The detailed workflow remains available directly:

```text
YouTube / local media
        ↓
inspection + caption discovery
        ↓
existing subtitles OR local whisper.cpp transcription
  ├─ conservative anti-ghost policy
  └─ targeted two-pass sparse/gap recovery
        ↓
normalized Segment[] timeline
        ├──────────────→ SRT / VTT / TXT
        ├──────────────→ original media + subtitles only
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
per-line timing fit
  ├─ subtitle-window target
  ├─ chained atempo, effective 0.30×–2.50×
  └─ small end-time correction pass
        ↓
soundtrack mix
  ├─ stable reduced original bed
  ├─ deeper subtitle-window dialogue/singing attenuation
  └─ gentle compressor + limiter
        ↓
track-aware remux/export
  ├─ replace primary audio
  ├─ add dubbed audio
  ├─ subtitle-only media package
  ├─ selectable subtitle tracks
  └─ video stream-copy unless explicitly downscaled
```

## Magic Flow orchestration

`magic_flow.py` owns only orchestration policy:

- source inspection;
- subtitle-route recommendation;
- dependency resolution between requested outputs;
- meaningful user-facing result paths;
- invoking existing transcription/translation/TTS/export engines.

### Subtitle-route recommendation

The default Auto policy prefers:

1. creator/embedded text subtitles;
2. already-installed Accurate Large-v3-Turbo-Q5 Whisper;
3. existing automatic captions;
4. another already-installed local Whisper model.

A key design rule is **no silent heavy downloads**. Recommendation is constrained to ready resources. Model preparation stays an explicit Settings action.

### Task dependencies

Magic Flow treats user-selected outputs as desired results, not implementation stages.

Examples:

```text
Subtitles
  → requires source subtitle timeline only

Translate
  → requires source subtitle timeline + contextual translation

Voice-over
  → requires source subtitle timeline + target-language timeline + Kokoro

Output media + Voice-over
  → requires full pipeline

Output media + Translate, no Voice-over
  → packages original media/audio + selectable subtitle tracks
```

This keeps the UI simple while preserving deterministic stage boundaries internally.

## Core design rules

1. Subtitle IDs/timestamps are stable data; translation/TTS do not rewrite them.
2. Subtitles are a complete output. Every downstream stage is optional.
3. One failed stage must not invalidate a simpler completed stage.
4. Caption cues remain subtitle data but are not translated as dialogue and are not spoken.
5. Hardware recommendations scale both translation model and llama.cpp KV/context allocation.
6. Heavy models download only after explicit user action; reusable executables/caches/runtimes are preferred.
7. Python virtual environments are never merged.
8. No silent cloud fallback and no silent contextual→OPUS downgrade.
9. Video re-encoding is never implied by audio/subtitle changes.
10. M1/low-memory compatibility is a runtime design constraint.
11. ASR recovery prefers uncertainty/gaps over invented speech.
12. DubLocal does not claim source separation when it is only attenuating a married mix.
13. Magic Flow and Detailed workflow must call the same underlying engines rather than fork behavior.
14. Auto language is a real state: detected language is consumed when known; contextual translation may identify it locally when unknown.

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

Relevant modules:

- `transcription.py` — base whisper.cpp integration;
- `transcription_guard.py` — severe hallucination/repetition protection;
- `transcription_v053.py` — selective missing-word/sparse-gap recovery.

Policy:

- ordinary speech may use Silero VAD when supported;
- Accurate music transcription disables rolling text context that can self-reinforce false lyrics;
- pathological near-duplicate runs are isolated and retried;
- severe persistent loops are suppressed rather than sent to translation/TTS;
- only a small number of suspicious sparse regions/gaps are rechecked;
- each recovery candidate is decoded twice independently with no context;
- both passes must agree closely;
- neighbour-echo candidates are rejected.

Low-memory Apple Silicon has stricter recovery limits. There is no second full-file pass and no extra ASR model.

## Adaptive contextual translation

`hardware_profile.py` chooses a conservative profile based on architecture and physical memory. The recommendation affects both model choice and runtime context allocation.

```text
Apple Silicon <12 GB      Qwen3 4B · 8k
Apple Silicon 12–23 GB    Qwen3 8B · 16k
Apple Silicon 24 GB+      Qwen3 8B + review · up to 24k
Intel <24 GB              Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context
```

`contextual_progress.py` owns translation execution/recovery. `contextual_policy.py` owns programme/context prompts and review instructions. Output is validated before becoming an SRT.

### Auto source language

When a concrete language is already known from subtitle metadata or Whisper, that state is reused.

When the UI still supplies `auto`, contextual translation performs lightweight subtitle-language identification inside the same Qwen runtime session, then translates with the resolved language. No second language-ID model is loaded.

## Voice architecture

Kokoro is a TTS backend, not the application architecture.

The TTS path:

1. preserves the original SRT;
2. creates a temporary speech-only timeline with bracket cues removed;
3. optionally analyses the source acoustic range;
4. chooses lower/higher voice presets per segment;
5. keeps one Kokoro runtime/model loaded;
6. writes segment WAV files plus a timing manifest.

## Timing and mixing

The timing layer measures actual generated WAV duration rather than assuming Kokoro speed is sufficient. FFmpeg `atempo` stages can be chained over the bounded 0.30×–2.50× effective range.

The mixing layer keeps the married source programme at a reduced bed and attenuates it further during source dialogue/singing windows. This is lightweight DSP; it is not a source-separation model.

## Export architecture

- MKV is the safest multi-track default.
- Generated source/translated subtitles are external inputs during remux and remain selectable tracks.
- Local Original video uses stream-copy.
- Explicit local downscale uses Apple VideoToolbox H.264.
- YouTube quality selection occurs before download where possible so final video can still be copied.
- Magic Flow can package subtitle tracks without generating/embedding DubLocal audio.

## Storage lifecycle

Temporary job data is created under the platform DubLocal cache, currently:

```text
~/Library/Caches/DubLocal/jobs/
```

Startup pruning removes stale/oversized job data. Persistent model registrations/shared caches are excluded from temporary cleanup.
