# DubLocal architecture

**Current beta: v0.6.0b1 — first packaged macOS beta**

DubLocal is a local-first media pipeline with two user-facing control layers over the same processing engines:

- **Magic Flow** — compact orchestration and hardware-safe recommendations.
- **Advanced workflow** — explicit stage-by-stage control.

Magic Flow is not a second backend. It resolves dependencies and calls the same source, transcription, translation, TTS, timing, mixing and remuxing modules used by the Advanced workflow.

## Product-level flow

```text
Magic Flow
  source + rights + output language + desired outputs
        ↓
route recommendation / dependency resolution
        ↓
existing DubLocal pipeline
```

The source boundary accepts three normal source families:

```text
YouTube ───────────────────────────────┐
Local file ────────────────────────────┼→ normalized/local media → pipeline
Course / authenticated website ───────┘
        │
        └→ SourceProvider acquisition only; no duplicate dubbing backend
```

Authenticated acquisition ends when a normal local `AcquiredMedia` object exists. Website adapters do not know about Whisper, Qwen, TTS or export. Protected DRM/encrypted streams are refused rather than bypassed.

The Advanced workflow remains available directly:

```text
YouTube / local / acquired authenticated media
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
local TTS provider
  ├─ Kokoro / registered compatible provider
  ├─ manual or automatic lower/higher vocal-range preset where supported
  └─ per-segment WAV + manifest
        ↓
per-line timing fit
        ↓
soundtrack mix
  ├─ stable reduced original bed
  ├─ deeper subtitle-window dialogue/singing attenuation
  └─ optional local vocal/accompaniment separation
        ↓
track-aware remux/export
  ├─ replace primary audio
  ├─ add dubbed audio
  ├─ subtitle-only media package
  ├─ selectable/burned subtitle options
  └─ video stream-copy unless explicitly downscaled
```

## Beta packaging architecture

0.6.0b1 deliberately does **not** freeze the Python application into a second self-contained runtime. The established updater already has strong safety semantics around a real official Git checkout, so the first beta package preserves that architecture.

```text
DubLocal-0.6.0b1-macOS-unsigned.dmg
        ↓ drag
/Applications/DubLocal.app
  ├─ AppleScript launcher applet
  ├─ established DubLocal.icns identity
  ├─ beta-bootstrap.sh
  └─ build-info.env (package version + exact source revision)
        ↓ first launch
~/Library/Application Support/DubLocal/app
  ├─ normal Git checkout
  ├─ branch: main
  ├─ origin: official ArrowSK/dublocal
  └─ .venv
        ↓
existing scripts/macos/launch-dublocal.sh
        ↓
python -m dublocal.launcher_runtime
```

For a new beta installation, the bootstrap clones official `main` and resets it to the exact commit recorded in the DMG. It does this only for the newly created managed checkout. Existing managed checkouts are never silently hard-reset. Branch and remote mismatches are treated as errors rather than overwritten.

This design preserves:

- the existing `normal_update.py` official-main safety checks;
- managed repair backups;
- the hardened detached restart path;
- user models/caches independently of the small `/Applications` bundle;
- normal source-level diagnostics during the beta period.

The beta DMG intentionally contains no AI weights, authenticated browser state, Demucs environment or Whisper model. Those remain app-managed resources.

### Unsigned beta boundary

The first beta is intentionally unsigned and not notarized. The packaging script validates that the generated `.app` has no code signature and creates an unsigned DMG plus SHA-256 checksum. User documentation requires the normal macOS Control-click/Open or Privacy & Security → Open Anyway path; it never recommends disabling Gatekeeper globally.

Future signing/notarization should change the distribution security layer, not the managed source/update architecture unless a later packaging milestone explicitly redesigns it.

## App identity and UI branding

`assets/macos/DubLocal.svg` is the single established visual source for the first beta. The macOS builder renders it to the `.icns` used by Finder/Dock. `beta_branding.py` mirrors that same geometry inline in the Gradio header, avoiding a second logo or another file-serving permission just for branding.

Branding is a wrapper around the current product builder; it does not replace Simple/Advanced UI behavior.

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
  → requires source subtitle timeline + target-language timeline + TTS provider

Media + Voice-over
  → requires full pipeline

Media + Translate, no Voice-over
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
12. Lightweight attenuation must not be described as true source separation.
13. Magic Flow and Advanced must call the same underlying engines rather than fork behavior.
14. Auto language is real state: detected language is consumed when known; contextual translation may identify it locally when unknown.
15. Authenticated website import ends at normalized local media; site adapters do not own processing stages.
16. Packaging must not create a second updater/restart implementation while the managed Git architecture is active.
17. Temporary cleanup must never delete models, authenticated sessions or finished user outputs.

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

TTS providers are downstream consumers of the same speech-only timeline rather than application architectures.

The TTS path:

1. preserves the original SRT;
2. creates a temporary speech-only timeline with bracket cues removed;
3. optionally analyses source acoustic range;
4. chooses compatible voice presets per segment when supported;
5. keeps the active provider/model loaded where possible;
6. writes segment WAV files plus timing data.

## Timing and mixing

Native TTS timing compares generated duration with each subtitle window and regenerates only genuine overflow where the provider supports speed control. The established FFmpeg correction path remains bounded rather than broadly stretching every generated line.

The lightweight mixing path keeps the married source programme at a reduced bed and attenuates it further during source dialogue/singing windows. Optional Demucs separation is a distinct local enhancement and falls back safely when unavailable.

## Export architecture

- MKV is the safest multi-track default.
- Generated source/translated subtitles remain selectable tracks unless burn-in is explicitly requested for a shareable output.
- Local Original video uses stream-copy where compatible.
- Explicit local downscale uses the established macOS encoding path.
- YouTube quality selection occurs before download where possible so final video can still be copied.
- Magic Flow can package subtitle tracks without generating/embedding DubLocal audio.

## Storage lifecycle

Temporary job data is created under the platform DubLocal cache, currently:

```text
~/Library/Caches/DubLocal/jobs/
```

`storage_cleanup.py` is the centralized boundary between disposable and protected data. Startup/normal safe points can prune stale jobs, translation cache entries, aged course manifests, bounded logs/repair backups and safely identifiable obsolete browser revisions.

Installed models, managed runtimes, shared Hugging Face data, authenticated website sessions and finished user outputs are protected from temporary cleanup. Settings → **Storage & Cleanup** exposes the same classification to the user.
