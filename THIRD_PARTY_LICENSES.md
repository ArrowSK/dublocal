# Third-party licences

This file tracks software that DubLocal imports, invokes, or may distribute.

DubLocal itself is licensed under Apache-2.0. Third-party software remains under its own licence.

| Component | Role | Distribution policy |
| --- | --- | --- |
| Gradio | Local web UI | Python dependency; retain upstream licence/notices |
| yt-dlp | YouTube metadata and caption access | Python dependency only; do not bundle unrelated executable builds |
| platformdirs | macOS-safe application/cache paths | Python dependency; retain upstream licence/notices |
| FFmpeg / ffprobe | Media inspection, subtitle extraction, audio/video processing | External tool during development. Any future bundled binary must have its exact build configuration and corresponding licence/source obligations documented before release |
| whisper.cpp | Planned local transcription backend | Not bundled yet. If distributed later, include upstream licence and model-weight metadata separately |
| Kokoro | Planned TTS backend | Not bundled yet. Code and every distributed model/voice asset must be recorded separately |

## Release rule

No binary, model, voice pack, translation pack, or other third-party asset may be added to a DubLocal release unless all of the following are recorded:

1. exact upstream project/model identifier;
2. exact version or immutable revision;
3. licence identifier and licence text/location;
4. whether redistribution is permitted;
5. whether commercial use is permitted;
6. attribution or source-offer obligations, if any;
7. a SHA-256 checksum for redistributed model/binary assets where practical.

The CI/release process should eventually validate `MODEL_LICENSES.json` and the packaged third-party manifest before publishing a release.
