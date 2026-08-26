# Third-party licences

DubLocal is open source under Apache-2.0. The software, models and media tools it uses keep their own licences. This file is the human-readable inventory; `MODEL_LICENSES.json` records model-specific machine-readable metadata.

Nothing in this project grants rights to third-party video, audio or subtitles. DubLocal users remain responsible for having the right or legal authority to process their media.

## Core application dependencies

| Component | Purpose | How DubLocal uses it |
| --- | --- | --- |
| Gradio | Local user interface | Python dependency; the UI is served only on the local machine by default |
| yt-dlp | YouTube metadata, captions and user-requested audio acquisition for local transcription | Python dependency only; DubLocal does not bundle unrelated yt-dlp executable builds |
| platformdirs | Safe macOS application/cache paths | Python dependency |
| FFmpeg / ffprobe | Media inspection, subtitle normalization/extraction and audio/video processing | Reuses an existing executable when present. Any future bundled binary must have its exact build configuration and corresponding licence/source obligations documented before release |
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

## Planned M4 component

| Component | Planned role | Rule before use/release |
| --- | --- | --- |
| Kokoro | Local TTS backend | Prefer a compatible existing local Kokoro runtime through the isolated worker mechanism. Any code/model/voice asset used by DubLocal must still have its exact upstream identity, licence and redistribution/commercial-use status recorded before public release |

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
