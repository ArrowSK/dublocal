# DubLocal architecture

**Current beta: v0.6.0b8 — explicit production composition**

DubLocal is a local-first media application with two user-facing control layers over one set of processing services:

- **Standard** — compact orchestration for normal jobs and queues.
- **Advanced** — explicit stage-by-stage control.

They are views over the same source, transcription, translation, voice, timing, mixing and export services. Beta 8 removes the old active pattern where importing a refinement module replaced functions/classes or temporarily replaced Gradio constructors to assemble the product.

## Production composition

The executable entry point is intentionally small:

```text
python -m dublocal.launcher_runtime
        ↓
launcher_runtime.py
        ↓
production_ui.build_app()
        ├─ Standard
        ├─ Advanced
        └─ Settings
```

`launcher_runtime.py` owns process startup/shutdown, housekeeping, local-only Gradio launch configuration and the single production UI import. It does not install feature patches.

The package root is metadata-only. Importing `dublocal` must not mutate another module or initialize product services.

## Standard processing path

```text
source selection
   ├─ YouTube
   ├─ Local file(s)
   └─ Course / Website
        ↓
production_queue.py / production_course.py
        ↓
production_pipeline.run_standard_workflow()
        ↓
source media + subtitle route
        ↓
transcription when required
        ↓
contextual translation when required
        ↓
voice generation when required
        ↓
audio mix / timing when required
        ↓
profile-aware media export
```

Queues are sequential. One failed queue item is recorded without discarding already completed items, and the Stop lifecycle prevents remaining queued work from starting.

## Advanced processing path

Advanced exposes the same engines in explicit stages:

```text
Source
  ↓
Subtitles
  ↓
Translate
  ↓
Voice-over
  ↓
Export
```

Advanced may expose additional controls, but it does not maintain a second translation, TTS or export backend.

## Source boundary

Three source families are supported by the product UI:

```text
YouTube ───────────────────────────────┐
Local file ────────────────────────────┼→ normalized/local media → processing pipeline
Course / authenticated website ───────┘
        │
        └→ SourceProvider acquisition only
```

Authenticated acquisition ends when the provider returns `AcquiredMedia`. Providers do not perform Whisper transcription, Qwen translation, voice synthesis or final media export.

The authenticated provider owns its security semantics directly:

- sign-in happens in a dedicated local browser profile;
- reusable credential/signature query values are redacted before errors/resume state are persisted;
- ordinary non-secret routing query parameters remain part of canonical lesson identity;
- signed HLS/DASH manifest URLs are still recognized by parsed URL path and inspected for encryption/DRM;
- DRM/encrypted media is refused, not bypassed;
- an explicit empty lesson selection means no lessons, never an implicit “all”.

These rules live in `authenticated_web.py`; there is no production runtime policy installer.

## Transcription

`transcription.py` is the canonical transcription route. The active path directly invokes the guard/recovery services rather than replacing transcription functions after import.

The current policy includes:

- optional whisper.cpp VAD where appropriate;
- Accurate/Large-v3-Turbo music-friendly command policy;
- repetition/hallucination detection;
- isolated recovery for suspicious repeated regions;
- smart sparse/gap recovery where the established safeguards accept it;
- stable SRT timestamps as the downstream contract.

## Contextual translation

`contextual_progress.py` owns the active Qwen translation execution policy.

The important invariants remain:

- hardware-selected Qwen model/profile;
- source-language Auto detection when required;
- programme/nearby/prior-translation context;
- adaptive output batching with bounded split/recovery behavior;
- exact subtitle-ID alignment;
- protected standalone caption tags;
- target-language/wrong-script validation;
- refusal to write an ambiguously mapped SRT;
- validated local translation cache.

Performance policy is part of the canonical implementation, not installed by replacing `translate_srt_contextual_with_progress` at launch.

## Voice architecture

`voice_engine.py` is the provider-neutral voice boundary. It routes to:

- official Kokoro languages;
- vetted/registered local providers such as Russian Kokoro;
- Hungarian via macOS system speech where available or Piper fallback.

`voice_selection.py` owns Auto voice selection/vocal-range planning. `voice_timing.py` owns the explicit timing-fit boundary. Provider preparation remains explicit; normal processing does not silently install large voice/runtime assets.

## Audio and export

The active audio and export services keep the established behavior:

- stable dialogue/soundtrack mixing;
- optional local vocal separation when prepared and selected/recommended;
- original audio retention when requested;
- MKV/MP4/Shareable MP4 output;
- selectable or burned subtitles where applicable;
- format-aware output profiles;
- VideoToolbox with software H.264 fallback where established;
- source video stream-copy when the selected output plan permits it.

Persistent output-profile policy lives in `output_profiles.py`; production orchestration consumes that policy explicitly.

## Product UI

`production_ui.py` constructs the real Gradio component tree directly. Production does not replace `gr.Button`, `gr.Dropdown`, `gr.Checkbox`, or another Gradio constructor to transform an older UI at build time.

The visible product terminology is therefore defined where the components are constructed: **Standard**, **Start Processing**, **Outputs**, **Options**, **Output files**, **Resolution limit**, and **Audio & delivery**.

## Storage and lifecycle

Temporary jobs live under the platform DubLocal cache and are managed by `storage_cleanup.py`. Automatic/manual temporary cleanup protects:

- installed models;
- authenticated website sessions;
- course resume state;
- finished user outputs.

`job_control.py` owns the process cancellation/shutdown lifecycle. The launcher invokes shutdown cleanup in a `finally` path so FFmpeg/model/tool child processes are not intentionally left behind after a normal stop/restart.

## Update and packaging architecture

The packaged macOS beta remains a small unsigned `.app`/DMG launcher around a managed official Git checkout:

```text
DubLocal-<version>-macOS-unsigned.dmg
        ↓ drag
/Applications/DubLocal.app
        ↓ bootstrap
~/Library/Application Support/DubLocal/app
  ├─ official ArrowSK/dublocal origin
  ├─ branch: main
  └─ private .venv
        ↓
scripts/macos/launch-dublocal.sh
        ↓
python -m dublocal.launcher_runtime
```

The first installation is pinned to the exact revision recorded in the package. Existing managed checkouts are not silently rewritten when their branch/remote/history violates updater safety rules.

Large AI models and browser sessions are not bundled into the DMG. The beta remains intentionally unsigned/not notarized, so first launch uses the normal per-app macOS approval path rather than disabling Gatekeeper.

## Architecture guardrails

`tests/test_production_architecture.py` treats the following as production regressions:

1. package import that performs executable initialization;
2. active production imports of historical overlay installers;
3. assignments such as `module.function = wrapper` into imported production modules;
4. Gradio constructor replacement such as `gr.Button = factory` in the active production path;
5. multiple competing launcher/UI composition roots.

Historical compatibility modules may remain in the source tree temporarily for regression comparison or incremental deletion, but they are not part of active production composition. Removing those files is a maintenance task, not a prerequisite for the runtime to be explicit.

## Core design rules

1. Subtitle IDs and timestamps are stable data; translation/TTS do not casually rewrite them.
2. Subtitles are a complete output; every downstream stage is optional.
3. One failed stage/item must not invalidate simpler work that completed successfully.
4. Caption cues remain subtitle data but are not translated/spoken as dialogue.
5. Heavy models download only after explicit user action.
6. No silent cloud fallback and no silent contextual→OPUS downgrade.
7. Source acquisition ends before transcription/translation/TTS/export.
8. Authenticated source handling must not persist reusable credentials or bypass DRM.
9. Video re-encoding is controlled by an explicit output plan, not implied by unrelated audio/subtitle changes.
10. Production features are composed through explicit calls/dependencies, not import-time mutation.
