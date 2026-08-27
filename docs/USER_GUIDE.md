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

### 3. Translate — Recommended for this Mac

Choose **From** and **To** languages. The normal contextual option is intentionally simple:

**Recommended for this Mac · Lightweight / Balanced / Best quality**

DubLocal detects architecture and physical memory locally and chooses the most sensible contextual profile for the machine instead of assuming every Mac should run the same model.

Current v0.4.2 recommendations:

- **8 GB Apple Silicon** → Qwen3 4B, single pass, 8k input-context cap.
- **16 GB Apple Silicon** → Qwen3 8B, single pass, 16k input-context cap.
- **24 GB+ Apple Silicon** → Qwen3 8B with the senior review pass, up to 24k input context.
- **Intel below 24 GB** → Qwen3 4B with a smaller context allocation.
- **Intel 24 GB+** → Qwen3 8B single pass with a reduced context cap.

These are conservative defaults, not statements that another profile is technically impossible.

The Main screen does not show a model spreadsheet. If you want the reasoning, open **Translation engine details** or **Settings → Model Manager → Contextual translation**. There DubLocal shows the detected Mac, recommended model, current input-context budget, actual llama.cpp context allocation and whether review is enabled.

#### Why this matters on an M1

A 5.03 GB 8B model can be a poor default on an 8 GB M1 once macOS, the model and llama.cpp KV cache all compete for unified memory.

DubLocal therefore uses the 2.5 GB Qwen3 4B profile on an 8 GB Apple Silicon Mac and also reduces the **actual llama.cpp context allocation**. It does not reserve a 32k KV cache and merely send a shorter prompt. That is the practical difference between a UI label and a real hardware-aware implementation.

#### What “contextual” means

DubLocal does not translate subtitle rows as unrelated sentences. It supplies the model with:

- nearby source dialogue before and after the current lines;
- sampled source context from across the programme;
- recent approved translations as terminology/style memory.

The usable context budget grows with programme duration until it reaches the cap for the current hardware profile.

Short media uses larger chunks. A short song can normally fit into one contextual translation chunk rather than several tiny independent requests.

#### Review pass

On the Best quality profile, the same loaded Qwen3 8B model performs a second senior-review pass against the original source lines and context.

The review is asked to correct:

- mistranslations;
- literal English-style syntax;
- unnatural target-language grammar;
- case/gender/number mistakes;
- incorrect word choice;
- untranslated ordinary words;
- inconsistent recurring phrases;
- inappropriate changes to slang or profanity.

The review is not allowed to invent missing ASR words or rewrite the material into something more literary.

Because the same model remains loaded, the review mainly adds processing time rather than another model-sized memory allocation. On 8 GB and 16 GB profiles it is not enabled by default.

If the review output itself is structurally broken, DubLocal keeps the already validated first-pass translation rather than replacing it with corrupt data.

#### First use of contextual translation

Open:

**Settings → Model Manager → Contextual translation**

and click **Prepare / verify contextual translation**.

DubLocal will:

1. detect the current Mac and select its recommendation;
2. reuse an existing compatible `llama.cpp` installation when available;
3. otherwise install `llama.cpp` through Homebrew;
4. download only the recommended Qwen3 model to the shared Hugging Face cache;
5. verify the pinned model checksum before registering it.

The two contextual model sizes are approximately:

- **Qwen3 4B Q4_K_M** — 2.5 GB;
- **Qwen3 8B Q4_K_M** — 5.03 GB.

Both are local Apache-2.0 model releases. DubLocal does not download both merely because both are supported.

If speed/storage matters more than contextual quality, choose **Fast legacy · OPUS · sentence-level** explicitly.

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

### Contextual translation

The accordion title itself includes the current recommendation, for example:

`Contextual translation · Lightweight · Qwen3 4B Q4_K_M`

or:

`Contextual translation · Best quality · Qwen3 8B Q4_K_M`

The status explains the hardware decision and shows both the recommended model and whether the alternate contextual model is already registered locally.

**Prepare / verify contextual translation** prepares only the recommended model. **Remove DubLocal contextual model** removes DubLocal's 4B/8B registrations/links while leaving the shared Hugging Face cache intact, so other local applications are not broken.

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

The goal is the best practical local translation for the current Mac, not a claim of perfect human translation.

Three facts remain important:

1. a stronger translator cannot reliably reconstruct speech that was already incorrectly transcribed;
2. even an 8B local model can make semantic or stylistic mistakes;
3. the best model in isolation is not necessarily the best product default if it causes memory pressure or extreme latency on the machine running it.

That is why DubLocal exposes Original/Translation side-by-side and chooses its default translation profile from the hardware rather than from a single universal marketing label.

For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

# What comes next

M5 adds:

- duration fitting against subtitle windows;
- original-audio ducking/mixing;
- stream-copy video export where compatible;
- **Replace primary audio** as the default dubbed-media mode;
- **Add dubbed audio as second track** as the optional multi-track mode.
