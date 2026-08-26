# Third-party licences

DubLocal is open source under Apache-2.0. The software, models and media tools it uses keep their own licences. This file is the human-readable inventory; `MODEL_LICENSES.json` records model-specific machine-readable metadata.

Nothing in this project grants rights to third-party video, audio or subtitles. DubLocal users remain responsible for having the right or legal authority to process their media.

## Core application dependencies

| Component | Purpose | How DubLocal uses it |
| --- | --- | --- |
| Gradio | Local user interface | Python dependency; the UI is served only on the local machine by default |
| yt-dlp | YouTube metadata, captions and user-requested audio acquisition for local transcription | Python dependency only; DubLocal does not bundle unrelated yt-dlp executable builds |
| platformdirs | Safe macOS application/cache paths | Python dependency |
| FFmpeg / ffprobe | Media inspection, subtitle normalization/extraction and audio/video processing | External development/runtime tool. Any future bundled binary must have its exact build configuration and corresponding licence/source obligations documented before release |
| whisper.cpp | Local speech-to-text engine | Optional external engine installed separately; Whisper model weights are opt-in |

## Optional M3 translation stack

Local subtitle translation is deliberately not part of the base Python installation. Choosing **Prepare translation** installs the optional translation runtime into DubLocal's own virtual environment and downloads only the model route required by the selected languages.

| Component | Purpose | Distribution policy |
| --- | --- | --- |
| PyTorch | Local tensor/inference runtime | Optional Python dependency; not bundled as a model |
| Transformers | Marian/OPUS model loading and generation | Optional Python dependency |
| SentencePiece | OPUS tokenizer support | Optional Python dependency |
| safetensors | Safe local model-weight loading | Optional Python dependency |
| `Helsinki-NLP/opus-mt-mul-en` | Allowlisted multilingual languages → English | Apache-2.0 model; pinned safetensors revision; downloaded only on explicit user request |
| `Helsinki-NLP/opus-mt-en-mul` | English → allowlisted multilingual languages | Apache-2.0 model; pinned safetensors revision; downloaded only on explicit user request |

The exact revisions and verified weight hashes used by M3 are recorded in `MODEL_LICENSES.json`. English ↔ another supported language needs one approximately 310 MiB OPUS model. A non-English ↔ non-English route uses English as a local pivot and therefore needs both models. DubLocal does not silently substitute a cloud translation API.

## Planned components

| Component | Planned role | Rule before release |
| --- | --- | --- |
| Kokoro | Local TTS backend | Code and every distributed/downloadable voice or model asset must be recorded separately before use in a public release |

## Release rule

No binary, model, voice pack, translation pack or other third-party asset may be added to a DubLocal release unless all of the following are recorded:

1. exact upstream project/model identifier;
2. exact version or immutable revision;
3. licence identifier and licence text/location;
4. whether redistribution is permitted;
5. whether commercial use is permitted;
6. attribution or source-offer obligations, if any;
7. a cryptographic checksum for redistributed/downloaded model or binary assets where practical.

The release process should eventually validate `MODEL_LICENSES.json` and the packaged third-party manifest before publishing a release.
