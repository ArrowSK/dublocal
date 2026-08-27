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
| Hugging Face Hub | Shared model downloads/cache | Core helper; models still download only on explicit user action |
| FFmpeg / ffprobe | Media inspection/extraction and later mixing/remuxing | Existing executable reused when available; any future bundled binary requires exact build/licence review |
| whisper.cpp | Local speech-to-text | Optional external engine; existing `whisper-cli` reused when present |

## v0.4.2 contextual translation — recommended quality path

The recommended quality translation path is local and uses a larger model plus a review pass.

| Component | Purpose | Licence / distribution policy |
| --- | --- | --- |
| `llama.cpp` | Local GGUF inference runtime / loopback llama-server | MIT upstream; DubLocal reuses an existing executable or can install it through Homebrew; not bundled in the development checkout |
| `Qwen/Qwen3-8B-GGUF` / `Qwen3-8B-Q4_K_M.gguf` | Default context-aware multilingual subtitle translation and review | Apache-2.0 upstream; not bundled; explicit download only; pinned immutable revision and SHA-256; shared Hugging Face cache |

The configured Qwen3 8B Q4_K_M weight is about 5.03 GB. Exact revision/hash are recorded in `MODEL_LICENSES.json`.

DubLocal reserves part of the model context for instructions/output and scales source context with programme duration. The same loaded model session can be reused for translation, recovery and the optional senior-review pass.

Removing the quality model from DubLocal removes only DubLocal's registration/link. It does not delete the shared Hugging Face snapshot or uninstall `llama.cpp`, because another local application may use them.

There is no cloud translation fallback.

## Historical Qwen3 4B development model

`Qwen/Qwen3-4B-GGUF` was used by the v0.4.1 development contextual translator. Real-language testing showed that it was not consistently strong enough for DubLocal's intended default quality level.

v0.4.2 does not select/download it. Its exact Apache-2.0 model metadata remains in `MODEL_LICENSES.json` for provenance. A previously downloaded shared-cache snapshot is not automatically deleted.

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

These models are not described as the recommended quality route because they translate subtitle text sentence-by-sentence and do not provide long-form dialogue context.

DubLocal never adds another application's `site-packages` to its own interpreter. Compatible Python environments are reused only by starting that environment's own Python as an isolated worker process.

## Whisper models

Whisper weights are downloaded only when requested and retain the whisper.cpp/OpenAI model licensing conditions represented in `MODEL_LICENSES.json`.

v0.4.2 additionally exposes the quantized Large-v3-Turbo-Q5 weight as an optional higher-accuracy transcription path for songs, accents and noisy audio. It is not bundled and is checksum-verified before use.

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

A model being present in the Hugging Face cache does not make it owned by DubLocal. DubLocal registrations can be removed without erasing shared snapshots another local application may need.

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
