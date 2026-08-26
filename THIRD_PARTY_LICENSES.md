# Third-party licences

DubLocal is open source under Apache-2.0. The software, models and media tools it uses keep their own licences. This file is the human-readable inventory; `MODEL_LICENSES.json` records model-specific machine-readable metadata.

Nothing in this project grants rights to third-party video, audio or subtitles. DubLocal users remain responsible for having the right or legal authority to process their media.

## Core application dependencies

| Component | Purpose | How DubLocal uses it |
| --- | --- | --- |
| Gradio | Local user interface | Python dependency; the UI is served only on the local machine by default |
| NumPy | Audio/timeline array processing | Core dependency from M4 onward; used to assemble the voice-only WAV without loading an entire long soundtrack into RAM |
| yt-dlp | YouTube metadata, captions and user-requested audio acquisition for local transcription | Python dependency only; DubLocal does not bundle unrelated yt-dlp executable builds |
| platformdirs | Safe macOS application/cache paths | Python dependency |
| FFmpeg / ffprobe | Media inspection, subtitle normalization/extraction and later audio/video processing | Reuses an existing executable when present. Any future bundled binary must have its exact build configuration and corresponding licence/source obligations documented before release |
| whisper.cpp | Local speech-to-text engine | Optional external engine; an existing `whisper-cli` is reused when present; Whisper model weights are opt-in |

## Optional M3 translation stack

Local subtitle translation is not part of the base Python installation. **Prepare translation** first looks for a compatible local runtime that already provides the required stack. If one is found in a recognized external environment, DubLocal may run it through an isolated worker process rather than copy those Python packages into DubLocal's virtual environment. If no compatible runtime exists, the optional `translation` extra is installed into DubLocal's own venv.

DubLocal never adds another application's `site-packages` directory to its own interpreter path.

| Component | Purpose | Distribution / reuse policy |
| --- | --- | --- |
| PyTorch | Local tensor/inference runtime | Optional; may run from DubLocal's venv or a compatible external Python worker; not redistributed by DubLocal as a model |
| Transformers | Marian/OPUS model loading and generation | Optional; same isolated-runtime reuse policy |
| SentencePiece | OPUS tokenizer support | Optional; same isolated-runtime reuse policy |
| safetensors | Safe local model-weight loading | Optional; same isolated-runtime reuse policy |
| `Helsinki-NLP/opus-mt-mul-en` | Allowlisted multilingual languages → English | Apache-2.0 model; pinned safetensors revision; explicit user preparation only; registered from the shared Hugging Face cache when possible |
| `Helsinki-NLP/opus-mt-en-mul` | English → allowlisted multilingual languages | Apache-2.0 model; pinned safetensors revision; explicit user preparation only; registered from the shared Hugging Face cache when possible |

The exact revisions and verified weight hashes are recorded in `MODEL_LICENSES.json`. English ↔ another supported language needs one approximately 310 MiB OPUS model. A non-English ↔ non-English route uses English as a local pivot and therefore needs both models.

Hugging Face snapshots use the normal shared cache. Removing a translation model from DubLocal removes DubLocal's registration/link but does not automatically delete the shared cache snapshot, because another local application may still rely on it.

DubLocal does not silently substitute a cloud translation API.

## M4 local voice generation

M4 adds Kokoro as the first local TTS backend.

| Component | Purpose | Distribution / reuse policy |
| --- | --- | --- |
| `kokoro` | Local text-to-speech runtime | Optional. DubLocal first reuses a compatible existing Python environment through an isolated worker. Only if none exists does **Prepare Kokoro** install the optional `kokoro` extra into DubLocal's own venv |
| `misaki` | Kokoro language/G2P support | Optional dependency when DubLocal must create its own Kokoro runtime; Japanese/Mandarin extras are included in that optional install |
| `hexgrad/Kokoro-82M` | Official Kokoro model and voice assets | Apache-2.0 according to the upstream project/model metadata used by this development baseline; not bundled; downloaded only after an explicit Prepare/Generate action; shared Hugging Face cache is reused |

Kokoro runs through `src/dublocal/kokoro_worker.py` when an external runtime is used. The worker is launched by that environment's own Python executable, receives a narrow JSON request, writes local segment WAV files/JSON results, and exits. DubLocal never imports another application's `site-packages` into its own process.

The current official Kokoro frontend exposed by DubLocal covers American English, British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese. DubLocal does not silently present Hungarian, Russian, German or other unsupported languages as Kokoro-capable.

M4 produces a voice-only WAV. It does not modify the source video's original audio. Soundtrack ducking/mixing and media remuxing are separate M5 work.

The first packaged DubLocal release must pin an immutable Kokoro model revision and complete the release manifest/checksum obligations before distribution. The current development build deliberately does not claim that a floating upstream snapshot is release-pinned.

Dependency reuse does not transfer or change a component's licence. DubLocal must comply with the licence of each component it invokes or distributes regardless of whether that component was installed by DubLocal or another local application.

## Release rule

No binary, model, voice pack, translation pack or other third-party asset may be added to a DubLocal packaged release unless all of the following are recorded:

1. exact upstream project/model identifier;
2. exact version or immutable revision;
3. licence identifier and licence text/location;
4. whether redistribution is permitted;
5. whether commercial use is permitted;
6. attribution or source-offer obligations, if any;
7. a cryptographic checksum for redistributed/downloaded model or binary assets where practical.

The release process should validate `MODEL_LICENSES.json` and the packaged third-party manifest before publishing a packaged GitHub Release.
