# DubLocal changelog

DubLocal is still in active development. Versions below describe development builds from `main`.

> **Current development build:** `v0.4.2.dev0` — **Subtitle Export + Translation Quality Pass**
>
> There is no packaged GitHub Release yet. The first packaged release will be published only after the Mac distribution work and release-level model/licence validation are complete.

## v0.4.2.dev0 — Subtitle Export + Translation Quality Pass — current

Real macOS testing exposed two independent quality problems: automatic captions can already contain incorrect words before translation starts, and the v0.4.1 Qwen3 4B translation backend was not consistently good enough for natural subtitle translation. v0.4.2 addresses both rather than masking either one.

### Subtitle/transcription workflow

- Subtitle output is now first-class in **2 · Subtitles**. Translation is optional.
- After existing-caption extraction or local Whisper transcription, the subtitle file can be downloaded immediately.
- **SRT** remains the default output. **WebVTT** and plain **TXT** can be selected without rerunning transcription.
- Added optional **Accurate · Large v3 Turbo Q5 · 547 MiB** local Whisper model for songs, accents and difficult/noisy audio. Base remains the smaller general-purpose default.
- YouTube automatic-caption tracks are labelled as a lower-confidence source for translation. DubLocal does not pretend that a translator can reliably reconstruct words the captioner already misheard.

### Translation-quality architecture

- Replaced Qwen3 4B as the recommended quality translator with pinned **Qwen3 8B Q4_K_M** (about 5.03 GB, Apache-2.0).
- The Qwen3 8B model is downloaded only on request, SHA-256 verified, and reused through the shared Hugging Face cache.
- The old 4B model is no longer selected or downloaded by v0.4.2. A previously downloaded shared-cache snapshot may remain until the user removes it through their normal Hugging Face cache management.
- A single loopback-only `llama-server` process loads the quality model once per translation job when available, rather than restarting `llama-cli` for each chunk. CLI remains a compatibility fallback.
- Short media uses larger chunks. A short song normally fits into a single contextual chunk instead of repeatedly loading/re-querying the model.
- **Best quality** performs a context-aware translation pass followed by a second senior-review pass using the same loaded model and the original source/context.
- The review pass explicitly corrects mistranslations, literal English calques, broken target-language grammar, untranslated ordinary words and inconsistent recurring phrases. A malformed review cannot overwrite an already validated draft.
- Target-language guidance is explicit. Russian output, for example, is instructed to use idiomatic contemporary Russian grammar rather than English syntax or pseudo-Russian transliterations.

### Safety and integrity of subtitle output

- Standalone caption cues such as `[MUSIC]`, `[APPLAUSE]` and `[LAUGHTER]` are structural tags. They bypass translation and are copied exactly.
- Runtime logs, model paths, llama.cpp banners, prompts and control characters are rejected before any translated SRT is written.
- Unexpected Chinese/Japanese/Korean/Hangul contamination is rejected for the current European translation targets.
- Cyrillic targets reject substantial untranslated Latin-script leakage; Latin-script targets reject substantial Cyrillic leakage.
- Subtitle IDs, order and original timestamps remain strict. Missing IDs are recovered with full context; if alignment still cannot be proven, DubLocal stops instead of writing a corrupt SRT.
- Automatic context/recovery never silently falls back to the legacy OPUS translator or a cloud service.

### UX

- Subtitles, translation and voice generation retain persistent stage states rather than relying only on transient notifications.
- The quality warning for automatic captions uses DubLocal's green/neutral visual language rather than introducing a new orange accent.

## v0.4.1.dev0 — M3.1 Contextual Translation

The original M3 OPUS implementation proved useful as a lightweight baseline but not good enough as the default for dialogue. It translated subtitle entries independently, which produced literal, awkward and sometimes nonsensical phrasing.

M3.1 introduced the first contextual translation path with Qwen3 4B and three context layers: programme-wide sampled source dialogue, nearby dialogue and rolling translated terminology/style memory. Context grew with programme duration from 4,096 to 24,576 input tokens inside a 32k context.

Real-language testing subsequently showed that the 4B model was not consistently strong enough for the intended quality target. v0.4.2 therefore supersedes it with Qwen3 8B plus a review pass rather than presenting prompt changes as a sufficient fix.

**Fast legacy · OPUS** remains available as the explicit low-storage/fast option.

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
- macOS venv identity-safe discovery, allowing compatible existing virtual environments to be reused correctly.

M4 deliberately stops before source-soundtrack editing. M5 adds duration fitting, audio ducking/mixing and stream-copy/remux output.

## v0.3.0.dev0 — M3 Local Translation

- Local subtitle translation with pinned Apache-2.0 Helsinki-NLP OPUS models.
- English ↔ supported-language translation with one model; non-English ↔ non-English through an English pivot.
- Side-by-side subtitle preview and translated SRT export with timestamps preserved.
- Shared Hugging Face cache reuse and compatible external Python-runtime reuse.
- Main/Settings navigation with Updates, Model Manager and Local Resources.

This remains the **Fast legacy** translation engine.

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
