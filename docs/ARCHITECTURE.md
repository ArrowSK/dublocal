# DubLocal architecture

**Current development build: v0.5.0.dev0 — M5 Local Dubbed Media Export**

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
  ├─ preserve original subtitle file
  └─ remove bracketed caption cues from temporary speech input only
        ↓
M4 Kokoro TTS
  ├─ reusable isolated Python runtime
  ├─ per-segment WAVs
  └─ synchronized voice-only WAV + manifest
        ↓
M5 timing fit
  ├─ borrow silence before next spoken segment
  └─ modest atempo speed-up, capped at 1.25×
        ↓
M5 soundtrack mix
  ├─ primary source soundtrack sidechain-ducked under voice
  └─ voice overlaid into new AAC dubbed mix
        ↓
M5 remux/export
  ├─ Replace primary audio — default
  └─ Add dubbed audio as second track
        ↓
video copied bit-for-bit where the selected container is compatible
```

## Core design rules

1. Subtitle IDs and timestamps are stable data. Translation changes text, not timing.
2. Subtitles are a complete output. Translation, TTS and dubbed-media export are optional downstream stages.
3. The default translator uses context; subtitle rows must not be treated as unrelated sentences.
4. Hardware recommendations account for architecture, physical/unified memory, model size and actual llama.cpp context allocation.
5. Longer programmes receive more contextual input only up to the active hardware profile's safe ceiling.
6. Caption cues are structural subtitle data. They remain in subtitle exports but are not translated as dialogue and are not spoken by TTS.
7. Heavy models download only after an explicit user action.
8. Reuse existing system executables, shared model caches and compatible external runtimes before installing duplicates.
9. Never merge Python virtual environments or inject another application's `site-packages` into DubLocal.
10. No silent cloud fallback and no silent downgrade from contextual translation to OPUS.
11. Model registrations require explicit licence metadata, immutable revisions and checksums.
12. Generated translation must pass alignment, runtime-leakage and target-script validation before an SRT is written.
13. One failed backend must not disable simpler completed stages.
14. Adding or replacing audio must not imply video re-encoding. M5 uses stream-copy for video whenever technically compatible.
15. DubLocal must not silently perform a long video transcode merely to satisfy a container request. If MP4 cannot remux the selected streams, the user is directed to MKV.

## Normalized subtitle timeline

`src/dublocal/timeline.py` defines:

```text
Segment
  index: int
  start_ms: int
  end_ms: int
  text: str
```

Integer milliseconds avoid accumulated timing drift. Existing captions and Whisper results are normalized into this representation before later stages.

`src/dublocal/subtitle_export.py` converts the stable timeline to SRT, WebVTT or TXT without rerunning transcription.

`src/dublocal/output_naming.py` exposes user-facing files with readable media-derived names rather than internal cache names. Examples:

```text
Movie Name.en.srt
Movie Name.es.vtt
Movie Name.dub.es.mkv
```

Internal job files continue to use disposable cache paths.

## M2 transcription

`src/dublocal/transcription.py` manages local `whisper-cli`, FFmpeg speech preparation and optional Whisper weights.

Base remains the normal starting model. Large-v3-Turbo-Q5 is the optional higher-accuracy local path for songs, accents, noisy material and obviously damaged automatic captions.

Language detection comes from whisper.cpp output when Auto detect is selected. `src/dublocal/language_utils.py` normalizes common ISO codes and full language labels such as `English`, `Russian` and `Spanish` so the detected result can be carried into the Translation `From` selector reliably.

Loading a new source resets the previous source-language state rather than reusing stale detection from an earlier job.

## M3 legacy translation

`src/dublocal/translation.py` retains the smaller Helsinki-NLP OPUS/Marian backend. It is useful when minimum storage or speed matters more than contextual quality, but its sentence-level architecture is not the recommended path for dialogue.

## Adaptive contextual translation

The contextual path is split into independently testable responsibilities:

```text
hardware_profile.py            architecture/RAM detection + recommendation tier
adaptive_contextual.py         choose/register Qwen3 4B or Qwen3 8B
contextual_translation.py      shared contextual primitives + pinned 4B model
contextual_quality_model.py    pinned 8B model registration/download
contextual_runtime.py          adaptive llama-server/llama-cli lifetime
contextual_policy.py           chunk/context plan + translation/review prompts
contextual_progress.py         orchestration, hardware cap, recovery, review, SRT writing
translation_quality.py         protected tags + target-output validation
contextual_recovery.py         strict ID-oriented recovery
```

### Hardware recommendation

Current conservative defaults are:

```text
Apple Silicon < 12 GB     Qwen3 4B · review off · 8,192 input cap
Apple Silicon 12–23 GB    Qwen3 8B · review off · 16,384 input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · 24,576 input cap
Intel < 24 GB             Qwen3 4B · review off · 6,144 input cap
Intel 24 GB+              Qwen3 8B · review off · 12,288 input cap
```

These are recommendations, not hard compatibility declarations. The Main UI receives only the resulting **Recommended for this Mac · Lightweight / Balanced / Best quality** label. Detailed reasoning remains in engine details and Model Manager.

### Context allocation versus prompt budget

DubLocal limits two different resources:

1. **Input budget** — how much source/context text goes into a translation request.
2. **llama.cpp runtime context** — how much KV/context capacity the runtime allocates.

Both are hardware-scaled. A low-memory M1 therefore does not reserve a 32k runtime context while receiving only an 8k prompt.

### Context policy

Before hardware capping, contextual input grows with programme duration:

```text
base input context       4,096 tokens
additional context       +128 tokens per programme minute
absolute input ceiling  24,576 tokens
model native context    32,768 tokens
```

Target chunk size is larger for short media:

```text
≤ 10 min      48 subtitle segments
≤ 30 min      36
≤ 90 min      28
> 90 min      24
```

Each chunk can receive programme-wide sampled context, nearby source dialogue and recent accepted translations.

### Gender, reference, idioms and metaphors

`contextual_policy.py` explicitly treats adjacent subtitle fragments as continuous discourse. The prompt now requires the model to use context to resolve grammatical gender, speaker/addressee/reference relationships, pronouns and recurring entities where the source supports them.

Idioms and phraseological expressions are translated for meaning, register and function rather than word-for-word. Metaphors and figurative imagery are preserved when they are intentional, but the model is explicitly told not to invent new imagery or unsupported facts.

Where the source genuinely does not establish gender or reference, the model is instructed not to fabricate it merely to make the target text more specific.

### Best-quality review pass

Hardware profiles that enable review use the same loaded Qwen3 8B model for a second pass against the original source, context and validated draft.

The review explicitly checks semantic mistranslation, literal calques, gender/case/number agreement, pronoun/reference consistency, idioms, phraseology, metaphors, recurring terminology and register/profanity consistency.

A malformed review cannot overwrite an already validated first-pass translation.

### Protected subtitle tags and output validation

Standalone cues such as `[MUSIC]`, `[APPLAUSE]` and `[LAUGHTER]` bypass translation and are copied exactly into the subtitle timeline.

Before translated text becomes SRT, DubLocal verifies:

- expected subtitle IDs are present exactly once;
- ordering and original timestamps are preserved;
- llama.cpp runtime/model/prompt text did not leak into subtitles;
- unexpected non-target script contamination is rejected;
- substantial wrong-script leakage is rejected for supported targets.

Recovery keeps the original context. If alignment/output cannot be validated, translation stops rather than writing a plausible-looking corrupt file.

## TTS preparation and M4 Kokoro

`src/dublocal/voice_text.py` creates a temporary speech-only SRT. It strips bracketed caption cues from text sent to TTS while leaving the user's actual subtitle file unchanged.

Examples:

```text
[MUSIC]              → no spoken segment
[LAUGHS] Hello       → Hello
Hello [APPLAUSE]     → Hello
```

If a timeline contains only non-spoken cues, voice generation stops with a clear error instead of producing meaningless speech.

`src/dublocal/tts.py` and `src/dublocal/kokoro_worker.py` then generate per-segment WAV files, a synchronized voice-only WAV and a timing manifest. A compatible external Kokoro environment can be reused through its own Python process; DubLocal does not import that environment into its own interpreter.

## M5 timing, mix and remux

`src/dublocal/m5.py` owns final dubbed-media export.

### Timing fit

M5 reads the Kokoro manifest. For each overflowing line it first extends the usable window into actual silence up to the next spoken segment. Only if that is insufficient does it apply FFmpeg `atempo`, capped at 1.25×.

Speech is never deliberately truncated. Any line that still exceeds the available window after the speed cap remains intact and is reported as a residual timing overflow.

### Soundtrack mix

M5 uses the first source audio stream as the soundtrack basis for the dubbed mix. That audio is resampled/formatted, sidechain-ducked while generated voice is active, and mixed with the fitted voice track into a new AAC soundtrack.

This is ordinary **ducking + overlay**. It is not source separation and does not claim to remove the original dialogue while independently preserving music/effects. True dialogue/background separation remains out of scope.

### Output modes

**Replace primary audio — default**

- DubLocal mixed soundtrack becomes the primary/default audio track.
- Additional original audio streams are preserved where possible.
- Original video is stream-copied where compatible.

**Add dubbed audio as second track**

- Original audio streams remain untouched.
- DubLocal mixed soundtrack is appended as another selectable audio stream.
- Dubbed track receives language/title/disposition metadata.
- Original video is stream-copied where compatible.

### Container policy

MKV is the recommended container because it tolerates mixed codec/track combinations well.

MP4 is supported only when the selected source streams can be remuxed into MP4 without video transcoding. When stream-copy is incompatible, DubLocal fails clearly and recommends MKV rather than silently re-encoding the movie.

Audio processing does require re-encoding of the new dubbed soundtrack. That does not imply video re-encoding.

## UI layering

`ui.py` remains the stable v0.4 workflow implementation.

`ui_v042.py` applies hardware-adaptive contextual policy to that layout.

`ui_v050.py` extends the same working design with v0.5 behavior: reliable language propagation, readable output naming, speech-only TTS preparation and the fifth **Export** stage. This adapter approach intentionally avoids replacing the functioning UI merely to add one downstream milestone.

Main is:

```text
1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export
```

Settings remains:

```text
Updates | Model Manager | Local Resources
```

## Dependency reuse

`src/dublocal/dependencies.py` reports/reuses FFmpeg/ffprobe, whisper.cpp, llama.cpp, the shared Hugging Face cache and compatible external Python environments.

Separate virtual environments remain separate. Supported external runtimes are invoked through dedicated worker processes.

## Updates, repair and temporary files

`src/dublocal/updater.py` distinguishes the running package, local Git checkout and official `origin/main`. Normal updates require a clean fast-forward. Repair can back up modified tracked files, restore official source and refresh the managed Python core while preserving models/caches/jobs/untracked files.

`src/dublocal/job_cache.py` owns temporary job cleanup:

```text
root       ~/Library/Caches/DubLocal/jobs/
max age    24 hours
max size   4 GiB
strategy   age first, then oldest-first size pruning
```

Temporary M5 downloads, fitted voice files, mixed audio and remuxed outputs are covered by the same lifecycle. Persistent model assets and the shared Hugging Face cache are outside it.

## Still out of scope

- OCR for image subtitle streams;
- speaker diarization and automatic multi-voice casting;
- dialogue/background source separation;
- semantic rephrasing/shortening specifically to fit difficult dub timing;
- signed/notarized macOS packaging.
