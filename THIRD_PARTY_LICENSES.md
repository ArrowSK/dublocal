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
| whisper.cpp | Local speech-to-text and optional VAD integration | Optional external engine; existing `whisper-cli` reused when present |

## v0.5.2 Whisper speech detection

v0.5.2 can use the official whisper.cpp VAD model to avoid decoding instrumental/silent regions as speech.

| Component | Purpose | Licence / distribution policy |
| --- | --- | --- |
| `ggml-org/whisper-vad` / `ggml-silero-v6.2.0.bin` | Tiny auxiliary speech detector for whisper.cpp VAD | MIT; not bundled; on-demand download; pinned immutable revision and SHA-256; stored with DubLocal Whisper assets |

The registered VAD asset is approximately 0.9 MiB. It is not a transcription/language model and does not replace the selected Whisper model. Exact revision, file URL, size and checksum are recorded in `MODEL_LICENSES.json`.

If the installed `whisper-cli` does not support VAD, or the auxiliary model cannot be obtained while offline, DubLocal falls back to conservative Whisper decoding without silently installing another heavy dependency.

## v0.4.2 adaptive contextual translation

The recommended contextual translation path is local and hardware-aware. DubLocal does not install the same model on every Mac.

| Component | Purpose | Licence / distribution policy |
| --- | --- | --- |
| `llama.cpp` | Local GGUF inference runtime / loopback llama-server | MIT upstream; DubLocal reuses an existing executable or can install it through Homebrew; not bundled in the development checkout |
| `Qwen/Qwen3-4B-GGUF` / `Qwen3-4B-Q4_K_M.gguf` | Lightweight contextual translation for low-memory Apple Silicon and modest Intel Macs | Apache-2.0 upstream; not bundled; explicit download only when recommended; pinned immutable revision and SHA-256; shared Hugging Face cache |
| `Qwen/Qwen3-8B-GGUF` / `Qwen3-8B-Q4_K_M.gguf` | Balanced/best contextual translation and optional senior review | Apache-2.0 upstream; not bundled; explicit download only when recommended; pinned immutable revision and SHA-256; shared Hugging Face cache |

Configured approximate weight sizes are 2.5 GB for Qwen3 4B Q4_K_M and 5.03 GB for Qwen3 8B Q4_K_M. Exact revisions/hashes are recorded in `MODEL_LICENSES.json`.

DubLocal scales both prompt/context use and the llama.cpp runtime context allocation according to detected architecture and memory. This is a runtime policy only; it does not alter the upstream model licence.

The same loaded model session can be reused for translation, recovery and, on the Best-quality profile, the optional senior-review pass.

Removing contextual models from DubLocal removes DubLocal's registrations/links. It does not delete shared Hugging Face snapshots or uninstall `llama.cpp`, because another local application may use them.

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

These models are not described as the recommended contextual route because they translate subtitle text sentence-by-sentence and do not provide long-form dialogue context.

DubLocal never adds another application's `site-packages` to its own interpreter. Compatible Python environments are reused only by starting that environment's own Python as an isolated worker process.

## Whisper models

Whisper transcription weights are downloaded only when requested and retain the whisper.cpp/OpenAI model licensing conditions represented in `MODEL_LICENSES.json`.

DubLocal additionally exposes the quantized Large-v3-Turbo-Q5 weight as an optional higher-accuracy transcription path for songs, accents and noisy audio. It is not bundled and is checksum-verified before use.

The Silero VAD auxiliary model described above is independent of the chosen Whisper transcription weight.

## M4 local voice generation

| Component | Purpose | Policy |
| --- | --- | --- |
| `kokoro` | Local TTS runtime | Optional; compatible existing Python environment is reused first through an isolated worker |
| `misaki` | Kokoro G2P/language support | Optional dependency when DubLocal owns the Kokoro runtime |
| `hexgrad/Kokoro-82M` | Official Kokoro model/voice assets | Apache-2.0 upstream baseline; not bundled; explicit/shared-cache download |

Kokoro runs through `src/dublocal/kokoro_worker.py` when an external runtime is selected. The worker receives a narrow JSON request, writes local WAV/JSON outputs and exits; DubLocal does not modify the external environment.

Official Kokoro frontends currently exposed cover American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese. A translation-capable language is not automatically a Kokoro-capable language.

M4 produces a voice-only WAV. M5 handles source-audio ducking/mixing and media remuxing.

## Russian third-party local TTS

Russian is intentionally represented as a separate local provider rather than as an official Kokoro language.

| Component | Purpose | Licence / distribution policy |
| --- | --- | --- |
| `zaakirio/kokoro-ru` v2 | Russian Kokoro-compatible weights and Sveta/Masha/Dima voice packs | Upstream model card reports OpenRAIL weights and Apache-2.0 code; not bundled; explicit preparation only; pinned source revision; persistent local provider snapshot |
| Dialogs Russian speech corpus | Source speech for the named Russian voices according to the model card | Dataset documentation states actor written consent for open/commercial use; retain source/licence attribution with commercial distribution records |
| RUAccent | Russian stress, `ё` restoration and homograph handling | MIT for the v1 system used by this integration; installed only with the optional Russian runtime |
| eSpeak NG | Russian phonemization engine used with the provider's acute-aware eSpeak data | GPL-3.0+ external executable; DubLocal does not bundle it and does not import the GPL Python `phonemizer` package |

The built-in provider records published SHA-256 values for both Russian model-weight files. Preparation resolves the pinned source revision, verifies declared hashes, stores the provider in persistent DubLocal application data and writes an install receipt. Generation then loads the local config, model, voice and eSpeak data paths; it does not depend on the `kokoro-ru` fork remaining reachable.

The eSpeak executable boundary is deliberate. DubLocal invokes a separately installed local command instead of incorporating eSpeak or the Python `phonemizer` package into the Apache-2.0 application. GPL permits commercial use, but this architecture is a distribution boundary rather than a legal guarantee about every future packaging arrangement. A packaged release that wants to ship eSpeak itself requires a separate GPL compliance review.

Russian model/data provenance is materially stronger than the Ukrainian candidate reviewed at the same time, but DubLocal still treats third-party uploader metadata as evidence rather than a warranty of rights. `MODEL_LICENSES.json` and the generated voice manifest preserve the declared provider licence and source information.

No Ukrainian TTS provider is enabled by default at this stage. A third-party Ukrainian provider may be evaluated later only after its recording/speaker/data chain of rights is sufficiently documented.

Custom TTS providers are described in `docs/TTS_PROVIDERS.md`. They are data manifests only: executable modules, scripts, entrypoints and shell commands are rejected. Remote custom providers require an immutable revision plus SHA-256 pins for their config/model/voice assets.

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
