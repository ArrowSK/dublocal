# DubLocal architecture

**Current development build: v0.4.0.dev0 / M4 Local Voice.**

DubLocal is split into replaceable stages. The Gradio UI coordinates work, while media access, transcription, translation, TTS and later media rendering remain separate modules.

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
M3 local translation (optional)
        ↓
Source or translated SRT
        ↓
M4 Kokoro TTS
  ├─ isolated compatible Python runtime
  ├─ per-segment WAV assets
  ├─ generation manifest
  └─ synchronized voice-only WAV
        ↓
M5 timing / duration fitting
        ↓
Original-audio ducking + speech overlay
        ↓
Stream-copy/remux or render/export
```

## Design rules

1. The UI orchestrates jobs but does not implement codecs/model inference itself.
2. Media input functions return serializable source descriptions used by UI state.
3. Expensive models are optional. The base application must launch without Whisper, translation or TTS weights installed.
4. Optional heavy Python stacks are not duplicated when a compatible runtime can be reused safely through an isolated worker process.
5. Virtual-environment `site-packages` directories are never mixed into another application's interpreter.
6. Shared model caches are preferred when the exact compatible assets can be reused.
7. Every downloadable model needs explicit licence/revision/checksum metadata before packaged distribution.
8. YouTube access remains separate from local-file processing and never implements DRM/access-control circumvention.
9. Intermediate outputs live in DubLocal job directories so later stages can reuse them without regenerating unrelated work.
10. A failed optional backend must not disable simpler workflows.
11. Expensive fallback actions are explicit; DubLocal does not silently start large downloads or inference.
12. Subtitle timing is stable data. Translation changes text, not source timestamps.
13. Normal app updates never overwrite local tracked edits. Repair is a separate recovery operation with backup/history safeguards.
14. Adding or replacing audio must not imply video re-encoding. M5 prefers video stream-copy whenever the container/codec combination allows it.

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

`src/dublocal/translation.py` uses two Apache-2.0 Helsinki-NLP OPUS/Marian models:

```text
many allowlisted languages → English
English → many allowlisted languages
```

English ↔ another language requires one model. Non-English ↔ non-English translation uses English as a local pivot and requires both.

Exact Hugging Face revisions containing safetensors weights are pinned and the main weight SHA-256 is verified before registration.

New M3 installs use the normal shared Hugging Face cache and create a lightweight DubLocal registration. Removing the DubLocal registration deliberately does not erase the shared snapshot.

Translation can run in DubLocal's own optional runtime or through `src/dublocal/translation_worker.py` under a compatible external Python environment.

## Reusable Python runtimes

`src/dublocal/dependencies.py` discovers controlled local resources:

- system executables (`ffmpeg`, `ffprobe`, `whisper-cli`);
- the standard/shared Hugging Face cache;
- compatible Python environments in known local application/project locations or explicitly supplied through `DUBLOCAL_EXTERNAL_PYTHONS`.

### macOS venv identity

A macOS venv commonly contains a `bin/python` symlink pointing to a framework Python binary. Two different venvs may therefore resolve to the same real executable even though running the two symlink paths produces different `sys.prefix`/`site-packages` environments.

Earlier discovery resolved those symlinks and could accidentally collapse separate venvs into one identity. M4 preserves the absolute venv entry-point path without resolving the symlink. This is required for reliable reuse of environments such as:

```text
~/dublocal/.venv/bin/python
~/narroam-studio/.venv/bin/python
```

They may share the same underlying framework Python while still being different package environments.

## M4 — Kokoro local voice generation

M4 adds `src/dublocal/tts.py` and `src/dublocal/kokoro_worker.py`.

### Runtime policy

The Kokoro runtime requirement is probed as a compatible set of modules (`kokoro`, NumPy, PyTorch and Hugging Face Hub).

Preparation order is:

```text
compatible existing runtime?
  ├─ yes → reuse it unchanged through worker process
  └─ no  → install DubLocal's optional [kokoro] extra
```

No external `site-packages` path is appended to DubLocal's interpreter.

### Worker boundary

`kokoro_worker.py` is intentionally self-contained enough to be executed by the selected external Python directly:

```text
external-python kokoro_worker.py request.json response.json
```

The request contains the Kokoro language frontend, voice, speed, model repo, output folder and subtitle segment texts. The worker loads Kokoro locally, chooses CUDA/MPS/CPU, falls back from MPS to CPU when necessary, writes one 24 kHz mono PCM WAV per segment, then returns JSON metadata.

The worker writes into DubLocal's own job directory; it does not modify the external application's files or environment.

### Voice-only timeline assembly

M4 keeps the source SRT start times. `tts.py` places each generated segment at its original `start_ms` and builds one voice-only WAV.

A generated voice line can be longer than its subtitle slot. M4 does not hide that. It records:

```text
voice_duration_ms
slot_ms
overflow_ms
```

If two generated segments overlap, the M4 voice-only preview mixes the overlap rather than shifting the later subtitle off its original start time. M5 uses the recorded overrun information to fit speech more intelligently.

The voice timeline mixer uses a NumPy memory-mapped float buffer so long programs do not require the full output waveform to live in RAM at once.

### M4 outputs

A voice job contains:

```text
segments/segment-000001.wav
segments/segment-000002.wav
...
voice-<language>-<voice>.wav
voice-manifest.json
```

The manifest records runtime identity, device, official model repo, language/frontend, voice, speed, source SRT and per-segment timing/duration data.

### Kokoro language boundary

Official Kokoro frontends exposed by M4 are American English, British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Translation and TTS capability are separate. A successful translation to Hungarian, Russian or German does not make Kokoro capable of pronouncing that language. DubLocal therefore leaves those targets subtitle-only rather than silently using an incorrect frontend.

## Main / Settings UI split

`src/dublocal/ui.py` keeps the processing path under **Main** and maintenance under **Settings**.

Settings contains:

- **Updates**;
- **Model Manager** (Whisper, OPUS, Kokoro);
- **Local Resources**.

The Main tab contains source/caption handling, transcription, translation and M4 voice generation, but not model install/remove operations.

## Updates, repair and launcher runtime

`src/dublocal/updater.py` distinguishes three identities:

```text
running Python package
local Git checkout
official origin/main
```

Normal updates verify official origin/main, require a clean fast-forward, refresh the managed editable package and validate its imported version/module path.

**Repair installation** can back up modified tracked files as a Git patch, restore official tracked source, refresh/verify the core and restart without deleting models, shared caches, generated jobs or untracked user files. It refuses to rewrite local commits/diverged history.

`src/dublocal/launcher_runtime.py` exposes only DubLocal's generated jobs directory to Gradio's allowed paths so SRT/WAV outputs can be downloaded without exposing arbitrary user directories.

## M5 boundary

M5 begins with the M4 manifest/timeline and adds:

- speech-duration fitting;
- original-audio ducking/mixing;
- default **Replace primary audio** mode;
- optional **Add dubbed audio as second track** mode;
- language/title/disposition metadata for audio tracks;
- `-c:v copy` video stream-copy whenever technically compatible;
- video re-encoding only when the chosen output container/codec combination makes stream-copy impossible, with an explicit user-facing explanation.

True dialogue/source separation is separate from ordinary ducking/overlay and must not be implied until implemented.

## Still out of scope after M4

- OCR for image subtitle streams;
- speaker diarization/multiple voices;
- dialogue/background source separation;
- automatic speech-duration fitting;
- original-audio ducking/mixing;
- final remuxed/rendered dubbed media;
- signed/notarized macOS packaging.
