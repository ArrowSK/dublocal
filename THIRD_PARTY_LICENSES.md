# Third-party licences

This file tracks software that DubLocal imports, invokes, or may distribute.

DubLocal itself is licensed under Apache-2.0. Third-party software remains under its own licence.

| Component | Role | Current distribution policy |
| --- | --- | --- |
| Gradio | Local web UI | Python dependency; retain upstream Apache-2.0 licence/notices |
| yt-dlp | YouTube metadata, caption access and user-authorized audio acquisition | Python dependency only; do not bundle unrelated executable builds |
| platformdirs | macOS-safe application/cache/model paths | Python dependency; retain upstream licence/notices |
| FFmpeg / ffprobe | Media inspection, subtitle extraction and audio preparation | External Homebrew/system tool in development builds. Any future bundled binary must document its exact build configuration and satisfy the corresponding LGPL/GPL obligations |
| whisper.cpp | Local speech transcription engine | External Homebrew/system tool for M2; upstream is MIT. Future bundled binaries must include upstream MIT notice and exact version/build metadata |
| ggerganov/whisper.cpp GGML models | Optional local Whisper model weights | Never bundled with DubLocal core. Downloaded only after an explicit user action. The upstream Hugging Face model repository declares MIT; exact model URL, checksum and metadata are recorded in `MODEL_LICENSES.json` |
| Kokoro | Planned TTS backend | Not bundled yet. Code and every distributed model/voice asset must be recorded separately before release |

## M2 model policy

DubLocal M2 exposes only a small allowlist of multilingual Whisper GGML models: `tiny`, `base`, and `small`. The user installs and removes them from the Local transcription panel. Downloads go directly to the upstream `ggerganov/whisper.cpp` Hugging Face repository and are checksum-verified before use.

DubLocal does not silently download a model during installation or transcription. The base application must continue to launch and extract existing subtitles when no Whisper model is installed.

## Release rule

No binary, model, voice pack, translation pack, or other third-party asset may be added to a DubLocal release unless all of the following are recorded:

1. exact upstream project/model identifier;
2. exact version or immutable revision where practical;
3. licence identifier and licence text/location;
4. whether redistribution is permitted;
5. whether commercial use is permitted;
6. attribution or source-offer obligations, if any;
7. a cryptographic checksum for redistributed or downloaded model/binary assets where upstream publishes one.

The release process should validate `MODEL_LICENSES.json` and the packaged third-party manifest before publishing a release.
