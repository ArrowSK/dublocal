# Third-party licences

DubLocal is open source under Apache-2.0. Software, model weights and media tools it invokes keep their own licences. `MODEL_LICENSES.json` is the machine-readable model registry; this file is the human-readable inventory.

Nothing here grants rights to third-party video, audio or subtitles. Users remain responsible for having the right or legal authority to process their media.

## Core application dependencies

| Component | Purpose | DubLocal policy |
| --- | --- | --- |
| Gradio | Local user interface | Python dependency; local-only server by default |
| NumPy | Timeline/audio array processing | Core Python dependency |
| yt-dlp | YouTube metadata/captions and explicit audio acquisition for local transcription | Python dependency; no DRM/access-control bypass |
| platformdirs | Application/cache paths | Core Python dependency |
| Hugging Face Hub | Shared model downloads/cache | Core helper from v0.4.1.dev0; models still download only on explicit user action |
| FFmpeg / ffprobe | Media inspection/extraction and later mixing/remuxing | Existing executable reused when available; any future bundled binary requires exact build/licence review |
| whisper.cpp | Local speech-to-text | Optional external engine; existing `whisper-cli` reused when present |

## M3.1 contextual translation — recommended path

The default translation path in **v0.4.1.dev0** is context-aware and local.

| Component | Purpose | Licence / distribution policy |
| --- | --- | --- |
| `llama.cpp` | Local GGUF inference runtime | MIT upstream; DubLocal reuses an existing executable or can install it through Homebrew; not bundled in the development checkout |
| `Qwen/Qwen3-4B-GGUF` / `Qwen3-4B-Q4_K_M.gguf` | Context-aware multilingual subtitle translation | Apache-2.0 upstream; not bundled; explicit download only; pinned immutable revision and SHA-256; shared Hugging Face cache |

DubLocal reserves part of Qwen3's native context for output/instructions and scales the source context budget with programme duration. Model identity and checksum are recorded in `MODEL_LICENSES.json`.

Removing the contextual model from DubLocal removes only DubLocal's registration/link. It does not delete the shared Hugging Face snapshot or uninstall `llama.cpp`, because another local application may use them.

There is no cloud translation fallback.

## M3 fast legacy translation

The original OPUS/Marian backend remains as an explicit smaller/faster option.

| Component | Purpose | Policy |
| --- | --- | --- |
| PyTorch | Marian inference runtime | Optional Python stack; may run in DubLocal or a compatible isolated external worker |
| Transformers | OPUS model loading/generation | Optional; same isolated-runtime policy |
| SentencePiece | OPUS tokenization | Optional |
| safetensors | Safe model-weight loading | Optional |
| `Helsinki-NLP/opus-mt-mul-en` | Supported languages → English | Apache-2.0; pinned safetensors revision/checksum; shared cache |
| `Helsinki-NLP/opus-mt-en-mul` | English → supported languages | Apache-2.0; pinned safetensors revision/checksum; shared cache |

These models are no longer described as the recommended quality route because they translate subtitle text sentence-by-sentence and do not supply long-form dialogue context.

DubLocal never adds another application's `site-packages` to its own interpreter. Compatible Python environments are reused only by starting that environment's own Python as an isolated worker process.

## M4 local voice generation

| Component | Purpose | Policy |
| --- | --- | --- |
| `kokoro` | Local TTS runtime | Optional; compatible existing Python environment is reused first through an isolated worker |
| `misaki` | Kokoro G2P/language support | Optional dependency when DubLocal owns the Kokoro runtime |
| `hexgrad/Kokoro-82M` | Official Kokoro model/voice assets | Apache-2.0 upstream baseline; not bundled; explicit/shared-cache download |

Kokoro runs through `src/dublocal/kokoro_worker.py` when an external runtime is selected. The worker receives a narrow JSON request, writes local WAV/JSON outputs and exits; DubLocal does not modify the external environment.

Official Kokoro frontends currently exposed cover American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese. A translation-capable language is not automatically a Kokoro-capable language.

M4 produces a voice-only WAV. M5 handles source-audio ducking/mixing and media remuxing.

## Shared-cache rule

A model being present in the Hugging Face cache does not make it owned by DubLocal. DubLocal registrations can be removed without erasing shared snapshots that another local application may need.

Dependency reuse also does not change a component's licence. DubLocal must comply with each component's licence whether that component was installed by DubLocal or already existed on the Mac.

## Release rule

No model, voice pack, binary or other third-party asset may be added to a packaged DubLocal release unless the release manifest records:

1. exact upstream identifier;
2. exact version or immutable revision;
3. licence identifier and licence-text/location;
4. redistribution permission;
5. commercial-use status;
6. attribution/source obligations;
7. cryptographic checksum where practical.

The release process must validate `MODEL_LICENSES.json` and the packaged third-party manifest before publishing a packaged GitHub Release.
