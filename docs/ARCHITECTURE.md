# DubLocal architecture

**Current development build: v0.3.0.dev0 / M3 Local Translation.**

DubLocal is intentionally split into replaceable stages. The Gradio UI coordinates work, while media access, transcription, translation, future TTS and rendering remain separate modules.

That separation matters because each stage has different dependencies, licences, failure modes and performance characteristics. It also lets DubLocal reuse compatible resources already present on a Mac without merging unrelated application environments.

## Pipeline

```text
Source
  ├─ YouTube
  └─ Local media
        ↓
Media inspection
        ↓
Subtitle acquisition
  ├─ embedded text subtitle
  ├─ creator caption
  ├─ automatic caption
  └─ local whisper.cpp transcription
        ↓
Normalized timed Segment[]
        ↓
M3 local translation
  ├─ source → English
  ├─ English → target
  └─ source → English → target
        ↓
Translated timed SRT
        ↓
M4 local TTS
        ↓
Timing / duration fitting
        ↓
Original-audio ducking + speech overlay
        ↓
Preview / render / export
```

## Design rules

1. The UI orchestrates jobs but does not implement codecs/model inference itself.
2. Media input functions return serializable source descriptions used by UI state.
3. Expensive models are optional. The base application must launch without Whisper, translation or TTS weights installed.
4. Optional heavy Python stacks are not automatically duplicated if a compatible runtime can be reused safely through an isolated worker process.
5. Virtual-environment `site-packages` directories are never mixed into another application's interpreter.
6. Shared model caches are preferred for identical pinned snapshots; application-specific registrations remain lightweight and removable.
7. Every downloadable model needs explicit licence/revision/checksum metadata.
8. YouTube access remains separate from local-file processing and never implements DRM/access-control circumvention.
9. Intermediate outputs live in DubLocal job directories so later stages can reuse them without regenerating unrelated work.
10. A failed optional backend must not disable simpler workflows.
11. Expensive fallback actions are explicit; DubLocal does not silently start large downloads or inference.
12. Subtitle timing is stable data. Translation changes text, not source timestamps.
13. Normal app updates never overwrite local tracked edits. Repair is a separate, explicit recovery operation with backup and history safeguards.

## M1 — media and caption foundation

M1 established local media inspection with `ffprobe`, embedded text-subtitle discovery/extraction through FFmpeg, YouTube metadata/caption discovery through the Python `yt-dlp` package, caption extraction, rights confirmation, the Matrix-inspired Gradio shell and branded macOS launcher.

## M2 — local transcription

`src/dublocal/transcription.py` adds external `whisper-cli` discovery, Apple Silicon Metal/Intel CPU paths, FFmpeg speech preparation, user-requested YouTube audio fallback, Tiny/Base/Small model management, checksum verification, timestamped SRT output and Whisper language-detection handoff to M3.

M2 was validated on an Apple Silicon Mac before Issue #1 was closed.

## Normalized source timeline

`src/dublocal/timeline.py` defines:

```text
Segment
  index: int
  start_ms: int
  end_ms: int
  text: str
```

Integer milliseconds avoid floating-point timing drift. `parse_srt()` and `segments_to_srt()` provide a stable round trip. Later subtitle stages preserve `start_ms` and `end_ms` unless a future editor explicitly changes timing.

## M3 — local subtitle translation

`src/dublocal/translation.py` is the first translation backend. The current route uses two Apache-2.0 Helsinki-NLP OPUS/Marian models:

```text
many allowlisted languages → English
English → many allowlisted languages
```

English ↔ another language requires one model. Non-English ↔ non-English translation uses English as a local pivot and requires both.

Exact Hugging Face revisions containing safetensors weights are pinned and the main weight SHA-256 is verified before registration.

### Shared model storage

New M3 installs use `huggingface_hub.snapshot_download()` with the normal Hugging Face cache rather than a private `local_dir`. This means the exact same repo/revision snapshot can be reused by multiple compatible local applications.

After verification, DubLocal creates a lightweight application-data symlink/registration pointing to that snapshot. Removing the model from DubLocal removes the registration/link but intentionally does not erase the shared Hugging Face snapshot. Legacy private DubLocal model folders remain readable for backwards compatibility.

### Reusable Python runtimes

`src/dublocal/dependencies.py` discovers controlled local resources. It can recognize:

- system executables (`ffmpeg`, `ffprobe`, `whisper-cli`);
- the standard/shared Hugging Face cache;
- compatible Python environments in known local application/project locations or explicitly supplied through `DUBLOCAL_EXTERNAL_PYTHONS`.

A Python virtual environment is treated as an isolation boundary. DubLocal never appends another environment's `site-packages` to `sys.path`.

For M3 translation, if the current DubLocal venv does not contain PyTorch/Transformers/SentencePiece/safetensors but a recognized external Python does, translation can run through `src/dublocal/translation_worker.py`. The worker receives a small JSON request, loads the verified local model, returns translated strings as JSON, and exits. This permits actual dependency reuse without cross-contaminating the two environments.

If no compatible runtime exists, **Prepare translation** installs the optional translation extra into DubLocal's own venv.

This worker architecture is intended to be reused by M4 Kokoro so an existing compatible Kokoro installation can be used without installing a second copy.

### Translation inference

Direct and worker inference use `AutoTokenizer` and `AutoModelForSeq2SeqLM` with `local_files_only=True`, `trust_remote_code=False` and safetensors. Apple Silicon prefers MPS; if a Marian operation fails on MPS, the pass falls back to CPU.

The current UI allowlist is English, Hungarian, Russian, German, French, Spanish, Italian, Portuguese, Polish, Ukrainian, Serbian and Croatian.

### M3 translated segment view

Translation uses a parallel record rather than mutating source segments:

```text
TranslatedSegment
  index: int
  start_ms: int
  end_ms: int
  source_text: str
  translated_text: str
```

This keeps source text available for side-by-side review and guarantees that translated SRT generation preserves the original timing.

A future project record can layer speaker/TTS data on top of these primitives:

```json
{
  "id": "000123",
  "start_ms": 74220,
  "end_ms": 77840,
  "source_language": "en",
  "source_text": "Where are you going?",
  "target_language": "de",
  "target_text": "Wohin gehst du?",
  "speaker": null,
  "tts_asset": null,
  "status": "translated"
}
```

## Updates, repair and launcher runtime

`src/dublocal/updater.py` now distinguishes three identities:

```text
running Python package
local Git checkout
official origin/main
```

Normal updates verify that `origin` resolves to `ArrowSK/dublocal`, require the `main` branch, allow only clean fast-forwards, refresh the managed editable package and validate its imported version/module path.

**Repair installation** is deliberately separate from normal update. If the managed runtime is stale it can refresh it in place. If tracked source files are modified and the user explicitly permits replacement, repair first writes a binary Git patch to `~/.dublocal/repair-backups/`, then restores tracked files from official `origin/main`, refreshes/verifies the core and schedules a clean restart. It does not delete untracked files or data/model/cache directories, and it refuses to rewrite local commits/diverged history.

`src/dublocal/launcher_runtime.py` launches Gradio with only DubLocal's generated jobs directory added to Gradio's allowed paths. This permits generated subtitle downloads without exposing arbitrary user directories.

## Still out of scope after M3

- OCR for image subtitle streams;
- local Kokoro TTS generation (M4 next);
- speaker diarization/multiple voices;
- dialogue/background separation;
- speech duration fitting;
- original-audio ducking and speech overlay;
- rendered dubbed video;
- signed/notarized macOS packaging.

M4 should consume the existing translated/source timeline and reusable-runtime layer rather than reaching back into media acquisition or transcription.
