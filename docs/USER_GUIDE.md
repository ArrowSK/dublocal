# DubLocal user guide

**Current development build: v0.4.2.dev0 — Subtitle Export + Translation Quality Pass**

DubLocal is intended to behave like a small Mac utility rather than an AI development console. Once installed, open **DubLocal.app** and use the local browser window it launches.

There are two top-level areas:

- **Main** — process the current media job.
- **Settings** — update/repair DubLocal and manage optional engines/models.

There is no packaged GitHub Release yet.

## Main: normal workflow

### 1. Load the source

Choose **YouTube** or **Local file**, then click **Load source**.

The Source card stays visible and reports the result, for example:

`✓ Loaded · OK · YouTube · Title · 6:15 · 2 caption tracks`

For a local file, DubLocal uses `ffprobe` to inspect streams. For YouTube it inspects metadata and available caption tracks without silently downloading the full video.

### 2. Create or reuse subtitles

This stage is a complete output by itself. You do **not** need to translate after transcription.

If a usable subtitle/caption track exists, select it and click **Use existing subtitles**.

If the track is missing, image-based or unsuitable, open the Whisper section and click **Transcribe locally**.

The subtitle stage keeps a persistent status such as:

`✓ Transcribed · OK · 34 timed segments · English`

and exposes the resulting subtitle file immediately.

#### Download format

Choose:

- **SRT** — default;
- **WebVTT** — useful for web video;
- **TXT** — plain text transcript.

Changing this selector after transcription converts the current subtitle timeline. It does not rerun Whisper.

#### Which Whisper model should I use?

- **Base · 142 MiB** — default; good balance for ordinary clear speech.
- **Small · 466 MiB** — stronger but slower.
- **Accurate · Large v3 Turbo Q5 · 547 MiB** — optional quality choice for songs, accents, noisy material or when automatic captions look wrong.

The model must be installed once under **Settings → Model Manager → Whisper** before use.

### Automatic YouTube captions are not ground truth

If a selected YouTube track is marked **automatic captions**, DubLocal shows a quality warning.

This is important: translation receives the words present in the subtitle timeline. If the automatic captioner heard the wrong word, a translator cannot reliably know what was actually spoken or sung without going back to the audio.

For obviously damaged source text, prefer local Accurate Whisper transcription before judging translation quality.

### 3. Translate — Best quality is the default

Choose **From** and **To** languages. The normal quality mode is:

**Best quality · Qwen3 8B + review · recommended**

This is deliberately heavier than the previous Qwen3 4B development backend because real-language testing showed that the 4B model could still produce literal grammar, poor word choices and mixed-language output.

#### What “contextual” means

DubLocal does not translate subtitle rows as unrelated sentences. It supplies the model with:

- nearby source dialogue before and after the current lines;
- sampled source context from across the programme;
- recent approved translations as terminology/style memory.

The usable context budget grows automatically with programme duration, from roughly **4,096 input tokens** for short material up to **24,576 input tokens** within the model's native 32k context.

Short media uses larger chunks. A short song can normally fit into one contextual translation chunk rather than several tiny independent requests.

#### Best quality uses a review pass

After the first contextual translation, the same loaded Qwen3 8B model performs a second senior-review pass against the original source lines and context.

The review is explicitly asked to correct:

- mistranslations;
- literal English-style syntax;
- unnatural target-language grammar;
- case/gender/number mistakes;
- incorrect word choice;
- untranslated ordinary words;
- inconsistent recurring phrases;
- inappropriate changes to slang or profanity.

The review is not allowed to invent missing ASR words or rewrite the material into something more literary.

If the review output itself is structurally broken, DubLocal keeps the already validated first-pass translation rather than replacing it with corrupt data.

#### First use of Best quality

Open:

**Settings → Model Manager → Contextual translation · Qwen3 8B · quality**

and click **Prepare / verify contextual translation**.

DubLocal will:

1. reuse an existing compatible `llama.cpp` installation when available;
2. otherwise install `llama.cpp` through Homebrew;
3. download the pinned Qwen3 8B Q4_K_M model (about 5.03 GB) to the shared Hugging Face cache;
4. verify the model SHA-256 before registering it.

The old Qwen3 4B development model is no longer selected in v0.4.2.

#### Why translation may take longer now

Best quality loads a larger local model and normally performs two passes. Quality rather than minimum latency is the point of this mode.

DubLocal reduces unnecessary overhead by keeping one loopback-only `llama-server` process alive for the entire job, so the model is loaded once. Short media also uses larger chunks to reduce repeated inference calls.

If speed/storage matters more than quality, choose **Fast legacy · OPUS · sentence-level** explicitly.

### Subtitle tags and integrity

Standalone cues such as:

- `[MUSIC]`
- `[APPLAUSE]`
- `[LAUGHTER]`

are not dialogue. DubLocal copies them exactly and does not send them to the translator.

Before a translated SRT is written, DubLocal checks:

- every expected subtitle ID is present exactly once;
- original ordering/timestamps are retained;
- llama.cpp runtime text or prompts did not leak into subtitles;
- unrelated CJK/Hangul characters did not appear in current European targets;
- Russian/Ukrainian output is not substantially contaminated with untranslated Latin-script text;
- Latin-script targets are not substantially contaminated with Cyrillic text.

If these checks fail and contextual recovery cannot repair the affected line, DubLocal stops instead of writing a corrupted subtitle file.

### 4. Generate a local voice track

Open **4 · Voice-over**.

Choose whether to speak:

- **Translated subtitles**, or
- **Source subtitles**.

Choose a supported language, voice and speed, then click **Generate voice track**.

M4 creates a synchronized voice-only WAV and timing diagnostics. It deliberately does not edit the original soundtrack yet.

M5 will add duration fitting, soundtrack ducking/mixing and media remuxing.

## Kokoro language coverage

Official Kokoro support currently exposed by DubLocal includes American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Translation supports additional targets such as Hungarian, Russian and German, but the official Kokoro backend cannot voice all of those languages. DubLocal does not silently use the wrong pronunciation frontend.

# Settings

## Updates

Use **Check for updates → Install update → Restart DubLocal**.

Normal updates are clean fast-forwards from official GitHub `main`. Tracked local edits are not silently overwritten.

**Repair installation** restores official tracked application files after saving a patch backup and refreshes the managed Python environment. It preserves models, shared caches and generated job data.

## Model Manager

### Whisper

Install only the transcription models you need. Base remains the default; Accurate Large-v3-Turbo-Q5 is optional.

### Contextual translation · Qwen3 8B · quality

This is the recommended translation backend.

The model is download-on-demand, uses the shared Hugging Face cache and is registered only after checksum verification.

Removing the DubLocal contextual model removes DubLocal's registration/link. It does not indiscriminately delete the shared Hugging Face cache or Homebrew `llama.cpp` installation.

### Fast legacy translation · OPUS

The older ~310 MiB OPUS model directions remain available when you intentionally want the smaller/faster sentence-level engine.

### Kokoro

DubLocal first looks for a compatible existing Kokoro environment. If found, it runs that backend through an isolated worker process rather than copying another environment's Python packages into DubLocal.

## Local Resources

This panel reports reusable:

- FFmpeg and ffprobe;
- `whisper-cli`;
- `llama.cpp` / `llama-cli` / `llama-server` when available;
- shared Hugging Face cache;
- compatible external Python runtimes such as Kokoro.

Python environments remain isolated.

# Temporary files

Working files live under:

`~/Library/Caches/DubLocal/jobs/`

They include temporary downloaded audio, 16 kHz Whisper WAVs, intermediate subtitles, per-job llama-server logs and voice-generation intermediates.

At normal launch DubLocal removes jobs older than 24 hours and caps this temporary job cache at 4 GiB, deleting the oldest jobs first if necessary.

Persistent AI models and the shared Hugging Face model cache are not treated as temporary job files.

# YouTube HTTP 429

YouTube can temporarily rate-limit caption or media delivery. DubLocal retries ordinary caption retrieval but does not bypass that restriction.

If captions remain blocked, local Whisper transcription is the intended fallback. If YouTube also refuses audio delivery, wait or use a local copy you have the right to process.

# Translation quality expectations

The goal of Best quality is substantially better local translation, not a claim of perfect human translation.

Two facts remain important:

1. a stronger translator cannot reliably reconstruct speech that was already incorrectly transcribed;
2. even an 8B local model can make semantic or stylistic mistakes.

That is why DubLocal exposes both Original and Translation in the preview and keeps the original timing/source timeline available for review.

For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

# What comes next

M5 adds:

- duration fitting against subtitle windows;
- original-audio ducking/mixing;
- stream-copy video export where compatible;
- **Replace primary audio** as the default dubbed-media mode;
- **Add dubbed audio as second track** as the optional multi-track mode.
