# DubLocal architecture

DubLocal is intentionally split into small replaceable stages. The Gradio UI coordinates work, but media access, transcription, translation, future TTS and rendering remain separate modules.

That separation matters because each stage has different dependencies, model licences, failure modes and performance characteristics.

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

1. The UI may orchestrate jobs but does not implement codecs or model inference itself.
2. Media input functions return serializable source descriptions used by UI state.
3. Expensive models are optional. The base application must launch without Whisper, translation or TTS weights installed.
4. Optional translation Python dependencies are also not part of the base install; M3 installs them only after an explicit user action.
5. Every model intended for download/distribution must have explicit licence/revision/checksum metadata.
6. YouTube access remains separate from local-file processing and never implements DRM/access-control circumvention.
7. Intermediate outputs live in DubLocal job directories so later stages can reuse them without regenerating unrelated work.
8. A failed optional backend must not disable simpler workflows. For example, translation failure does not prevent extracting an SRT.
9. Expensive fallback actions are explicit. DubLocal may recommend Whisper or model preparation, but it does not silently start long inference or large downloads.
10. Subtitle timing is stable data. Translation changes text, not source timestamps.

## M1 — media and caption foundation

M1 established:

- local media inspection with `ffprobe`;
- embedded text-subtitle discovery/extraction with FFmpeg;
- YouTube metadata and caption discovery through the Python `yt-dlp` package;
- YouTube caption extraction;
- rights confirmation;
- the Matrix-inspired local Gradio shell;
- branded macOS launcher.

## M2 — local transcription

`src/dublocal/transcription.py` adds:

- external `whisper-cli` discovery;
- Apple Silicon Metal path and Intel CPU compatibility path;
- FFmpeg preparation to 16-bit 16 kHz mono WAV;
- user-requested YouTube audio acquisition for transcription fallback;
- Tiny/Base/Small multilingual Whisper model manager;
- model checksum verification;
- SRT output and normalized segment parsing;
- Whisper JSON output so Auto mode can carry the detected spoken language into M3.

## Normalized source timeline

`src/dublocal/timeline.py` defines:

```text
Segment
  index: int
  start_ms: int
  end_ms: int
  text: str
```

Integer milliseconds avoid floating-point timing drift. `parse_srt()` and `segments_to_srt()` provide a stable round trip.

All later subtitle stages should preserve `start_ms` and `end_ms` unless the user explicitly edits timing in a future editor.

## M3 — local subtitle translation

`src/dublocal/translation.py` is the first translation backend.

M3 deliberately uses a small, licence-controlled model set rather than downloading arbitrary Hugging Face models. The current route consists of two Apache-2.0 Helsinki-NLP OPUS/Marian models:

```text
many allowlisted languages → English
English → many allowlisted languages
```

English ↔ another language requires one model. A non-English ↔ non-English translation uses English as a local pivot and therefore requires both.

The model manager pins exact Hugging Face revisions containing safetensors weights and verifies the downloaded `model.safetensors` SHA-256 before use. Only required configuration/tokenizer/model files are downloaded into the macOS application-data directory; model folders are outside the Git checkout.

The optional inference stack is installed only after **Prepare translation**:

```text
PyTorch
Transformers
SentencePiece
safetensors
```

Inference uses `AutoTokenizer` and `AutoModelForSeq2SeqLM` with `local_files_only=True`, `trust_remote_code=False` and safetensors. Apple Silicon prefers MPS. If a Marian operation is unsupported on MPS, the translation pass falls back to CPU.

The current UI allowlist is intentionally smaller than the upstream 120-language model coverage. M3 enables English, Hungarian, Russian, German, French, Spanish, Italian, Portuguese, Polish, Ukrainian, Serbian and Croatian after validating their OPUS identifiers.

### M3 translated segment view

Translation uses a parallel record rather than mutating the source segment:

```text
TranslatedSegment
  index: int
  start_ms: int
  end_ms: int
  source_text: str
  translated_text: str
```

This keeps the source text available for side-by-side review and guarantees that translated SRT generation can preserve the exact original timing.

A future project record can layer additional information without replacing these timing primitives:

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

## Updater and local runtime

`src/dublocal/updater.py` performs user-initiated Git updates only. It fetches the configured upstream, requires a clean fast-forward, refuses dirty/diverged/ahead histories, refreshes the active editable Python package and schedules a restart through the macOS launcher.

`src/dublocal/launcher_runtime.py` launches Gradio with only DubLocal's generated jobs directory added to Gradio's allowed paths. This avoids exposing arbitrary user directories while allowing generated subtitle files to be downloaded from the local UI.

## Still out of scope after M3

- OCR for image subtitle streams;
- local Kokoro TTS;
- speaker diarization/multiple voices;
- dialogue/background separation;
- speech duration fitting;
- original-audio ducking and speech overlay;
- rendered dubbed video;
- signed/notarized macOS packaging.

M4 should build TTS on the translated/source timeline rather than reaching back into media acquisition or transcription.
