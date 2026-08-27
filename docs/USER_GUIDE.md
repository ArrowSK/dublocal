# DubLocal user guide

**Current development build: v0.4.1.dev0 — M4 Local Voice + M3.1 Contextual Translation**

DubLocal is meant to feel like a small Mac utility. Once installed, start **DubLocal.app** and work in the local browser window it opens.

There are two top-level areas:

- **Main** — process the current video/audio job.
- **Settings** — update/repair DubLocal and manage optional local resources.

There is no packaged GitHub Release yet.

## Main: the normal workflow

### 1. Choose the source

Choose **YouTube** or **Local file**, then click **Load source**.

The Source card itself shows `Loading source…` and then a persistent `Loaded · OK` summary with the title, duration and caption-track count.

For a local file, DubLocal uses `ffprobe` to inspect video/audio/subtitle streams. For YouTube, it inspects the remote video and available captions without silently downloading the full media.

### 2. Get timed source subtitles

If a usable caption/subtitle track exists, choose it and click **Use existing subtitles**.

If captions are missing, image-based, or YouTube temporarily refuses caption delivery, use **Transcribe locally** with Whisper.

The Subtitles stage shows its own persistent state such as `Transcribing locally…` and then `Transcribed · OK`.

#### Download immediately — translation is optional

A finished source timeline is a complete deliverable by itself. You do not need to translate it.

Choose **Download format** before or after extraction/transcription:

- **SRT** — default and recommended for subtitles;
- **WebVTT** — useful for web/video players;
- **TXT** — plain transcript without timestamps;
- **CSV** — start/end timestamps plus text.

Changing the format after transcription re-exports the existing timeline; Whisper does not run again.

Internally DubLocal keeps a normalized SRT timeline for later translation and voice generation regardless of which download format you choose.

Whisper model installation lives in **Settings → Model Manager → Whisper**.

For ordinary speech, **Base** is a good starting point. Song lyrics and noisy material are significantly harder ASR tasks; if the source transcript itself contains wrong words, use **Small** before judging translation quality. A translator cannot reliably recover words that Whisper never recognized.

### 3. Translate — Contextual quality is the default

Choose the source language and target language, then leave **Contextual quality · Qwen3 4B · recommended** selected for normal use.

Unlike the old sentence-level OPUS path, Contextual quality does not treat every subtitle row as an isolated sentence. Translation receives:

- nearby source lines before and after the current material;
- sampled dialogue from across the programme;
- recent translated lines as rolling terminology/style memory.

This matters for pronouns, names, relationships, slang, jokes, callbacks, profanity and tone.

#### Longer video = larger context

DubLocal calculates a context budget automatically from programme duration.

The current v0.4.1.dev0 policy starts at about **4,096 input tokens** for short material and adds context as duration grows, up to **24,576 input tokens**. Qwen3's native context remains larger than that, leaving room for instructions and generated subtitles.

Short material is packed into fewer translation chunks when it safely fits. This reduces overhead and gives a short song or clip more continuous context.

For a translation job DubLocal now starts one local `llama-server`, loads Qwen once, reuses that model session for every chunk/recovery request, and shuts the server down when the job finishes. This avoids repeatedly reloading a 2.5 GB model for every chunk.

Translation uses a strict DubLocal subtitle-line protocol over the local HTTP API. `llama.cpp` startup logs, prompt echoes and terminal control characters are never accepted as subtitle text.

#### First use

If Contextual quality is not ready:

**Settings → Model Manager → Contextual translation · Qwen3 4B → Prepare / verify contextual translation**

This may install/reuse `llama.cpp` and download the ~2.5 GB model once. Model files use the shared Hugging Face cache and are checksum-verified.

Then return to Main and click **Translate subtitles**.

DubLocal preserves the original subtitle IDs, segment count and timestamps. The preview shows **Translation** first and **Original** beside it.

### Fast legacy translation

If you explicitly choose **Fast legacy · OPUS · sentence-level**, DubLocal uses the older M3 Marian/OPUS backend.

It is smaller and faster, but it does not provide the same dialogue context. It remains available for low-storage or quick jobs rather than being silently used as a fallback.

### 4. Generate a local voice track

Choose whether to speak:

- **Translated subtitles**, or
- **Source subtitles**.

Choose a supported voice language, voice and speed, then click **Generate voice track**.

M4 creates:

- per-segment WAV files;
- one synchronized voice-only WAV;
- a JSON manifest;
- a timing table showing which lines overrun their subtitle windows.

M4 deliberately does not modify the original soundtrack yet. M5 handles duration fitting, ducking/mixing and media remuxing.

## Kokoro language coverage

Official Kokoro support exposed in the current build includes American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Translation supports additional targets such as Hungarian, Russian and German, but official Kokoro cannot voice those targets. DubLocal does not pretend otherwise or silently apply the wrong pronunciation frontend.

# Settings

## Updates

Use **Check for updates → Install update → Restart DubLocal**.

Normal updates are clean fast-forwards from official GitHub `main`. Tracked local edits are not overwritten.

**Repair installation** can restore official tracked program files after saving a patch backup and refresh the managed Python core. Models, shared caches and generated jobs are preserved.

## Model Manager

### Whisper

Install/verify Tiny, Base or Small. Models are downloaded only when requested.

### Contextual translation · Qwen3 4B

This is the recommended translation backend.

**Prepare / verify contextual translation**:

1. reuses existing `llama.cpp` when available;
2. otherwise installs it through Homebrew;
3. downloads the pinned official Qwen3 4B Q4_K_M model (~2.5 GB) to the shared Hugging Face cache;
4. verifies its SHA-256 before enabling it.

Removing the DubLocal contextual model removes DubLocal's registration/link, not the underlying shared cache snapshot or `llama.cpp` installation.

### Fast legacy translation · OPUS

The two older ~310 MiB OPUS directions remain available here. Use them only when you deliberately want the smaller/faster sentence-level engine.

### Kokoro

DubLocal first looks for a compatible existing Kokoro environment. If found, it uses that environment's Python through an isolated worker rather than copying its packages. Missing official model/voice assets use the shared Hugging Face cache.

## Local Resources

This panel reports reusable:

- FFmpeg and ffprobe;
- `whisper-cli`;
- `llama-cli` and `llama-server`;
- the shared Hugging Face cache;
- compatible external Python runtimes such as Kokoro.

Python environments remain isolated: another application's `site-packages` is never injected into DubLocal's interpreter.

# YouTube HTTP 429

YouTube can temporarily rate-limit caption/media delivery. DubLocal retries ordinary caption retrieval but does not evade the restriction.

If captions remain blocked, use local Whisper transcription. If YouTube also blocks audio delivery, wait or use a local copy you have the right to process.

# Translation quality expectations

Context improves translation substantially, but a 4B local model can still make semantic or stylistic mistakes. The preview is there for review, especially before generating speech or distributing subtitles.

Translation quality is also bounded by source quality. If Whisper transcribes a lyric, name or sentence incorrectly, contextual translation should not confidently invent a replacement. For difficult songs/noisy speech, first improve the source transcription (for example with Whisper Small), then translate.

DubLocal validates every expected subtitle ID before writing the translated SRT. Runtime banners, prompt echoes and malformed/misaligned output are rejected instead of being written into subtitles.

For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

# What comes next

M5 adds:

- duration fitting against subtitle windows;
- original-audio ducking/mixing;
- stream-copy video export where compatible;
- **Replace primary audio** as the default dubbed-media mode;
- **Add dubbed audio as second track** as the optional multi-track mode.
