# DubLocal changelog

DubLocal is still in active development. Versions below describe development builds from `main`.

> **Current development build:** `v0.4.1.dev0` — **M4 Local Voice + M3.1 Contextual Translation**
>
> There is no packaged GitHub Release yet. The first packaged release will be published only after the Mac distribution work and release-level model/licence validation are complete.

## v0.4.1.dev0 — M3.1 Contextual Translation — current

The original M3 OPUS implementation proved useful as a lightweight baseline but not good enough as the default for dialogue. It translated subtitle entries independently, which produced literal, awkward and sometimes nonsensical phrasing.

M3.1 changes the default translation path rather than trying to hide that limitation.

### Added

- **Contextual quality** as the default translation mode.
- Official `Qwen/Qwen3-4B-GGUF` Q4_K_M (about 2.5 GB) as the local quality model.
- `llama.cpp` as the local inference runtime; an existing installation is reused first, otherwise Model Manager can install it through Homebrew.
- Exact immutable model revision and SHA-256 verification before DubLocal registers the shared model file.
- A translation context made from three layers:
  - programme-wide sampled source dialogue;
  - nearby source dialogue before and after the lines being translated;
  - recent translated lines carried forward as terminology/style memory.
- A context budget that automatically grows with programme duration, from 4,096 tokens for short material up to a 24,576-token input ceiling within the model's native 32k context.
- Chunked subtitle translation with constrained JSON output so subtitle IDs, segment count and timestamps stay aligned.
- Explicit instructions to preserve speaker intent, recurring names, slang, jokes, profanity/register and non-dialogue cues.
- `llama.cpp` reporting under **Settings → Local Resources**.

### Kept deliberately

- **Fast legacy · OPUS** remains available as an explicit low-storage/fast choice.
- Existing OPUS downloads are not removed during upgrade.
- There is no silent cloud fallback and no silent downgrade from Contextual quality to OPUS.

M3.1 is not declared quality-validated until a real long-form translation is tested on the target Mac. Issue #9 tracks that validation.

## v0.4.0.dev0 — M4 Local Voice

M4 added the first local speech-synthesis stage without changing the source movie soundtrack.

- Kokoro as the first local TTS backend.
- Reuse of a compatible existing Kokoro virtual environment through a separate worker process.
- Fallback Kokoro preparation only when no reusable runtime exists.
- Official Kokoro language/voice selectors.
- Voice-only WAV generation from source or translated SRT.
- Per-segment WAV assets and a JSON generation manifest.
- Timeline assembly that preserves subtitle start times and reports overruns.
- Shared Hugging Face cache reuse.
- macOS venv identity-safe discovery, allowing environments such as `~/narroam-studio/.venv/bin/python` to be reused correctly.

M4 deliberately stops before source-soundtrack editing. M5 adds duration fitting, audio ducking/mixing and stream-copy/remux output.

## v0.3.0.dev0 — M3 Local Translation

- Local subtitle translation with pinned Apache-2.0 Helsinki-NLP OPUS models.
- English ↔ supported-language translation with one model; non-English ↔ non-English through an English pivot.
- Side-by-side subtitle preview and translated SRT export with timestamps preserved.
- Shared Hugging Face cache reuse and compatible external Python-runtime reuse.
- Main/Settings navigation with Updates, Model Manager and Local Resources.

This remains the **Fast legacy** translation engine in v0.4.1.dev0.

## v0.2.0.dev0 — M2 Local Transcription

- Local `whisper.cpp` transcription.
- Tiny, Base and Small Whisper model management with checksum verification.
- Auto/manual source language selection.
- Timestamped SRT generation and preview.
- YouTube/local-file transcription fallback.
- First in-app GitHub updater.
- Gradio generated-file path fix.

## v0.1.0.dev0 — M1 Source and Captions

- Matrix-inspired Gradio shell.
- Local media inspection with ffprobe.
- YouTube metadata/caption discovery with yt-dlp.
- Existing subtitle/caption extraction.
- Branded macOS launcher and DubLocal icon.
