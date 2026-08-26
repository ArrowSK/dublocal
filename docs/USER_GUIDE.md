# DubLocal user guide

**Current development build: v0.3.0.dev0 — M3 Local Translation**

DubLocal is meant to feel like a small Mac utility, not a Python project. Once installed, start it with **DubLocal.app** and use the local browser window it opens.

The interface is now split into two top-level areas:

- **Main** — process the current video/audio job.
- **Settings** — maintain DubLocal itself and optional local AI resources.

Inside **Settings** there are three subtabs: **Updates**, **Model Manager**, and **Local Resources**.

> There is no packaged GitHub Release yet. `v0.3.0.dev0` is the current development build on `main`. See [CHANGELOG.md](../CHANGELOG.md) for the build history.

## Before you start

Local video/audio files are not uploaded to a cloud transcription or translation service. Whisper and OPUS translation run on your Mac.

YouTube is different because the source itself is remote: DubLocal has to contact YouTube to inspect the video, request captions, or fetch audio when you explicitly start local transcription. Process only media you have the right or legal authority to use.

# Main

## 1. Choose the source

At the top choose **YouTube** or **Local file**.

For YouTube, paste one video URL and click **Scan source**. DubLocal shows the title and any creator/automatic caption tracks it can discover.

For a local file, select the media and click **Scan source**. DubLocal uses your existing local `ffprobe` installation to inspect the streams and list embedded subtitle tracks.

## 2. Get timed source subtitles

You can either reuse existing captions or make new ones from the audio.

### Existing subtitles

Choose the subtitle/caption track, confirm that you have the right to process the media, then click **Extract existing subtitles**.

DubLocal normalizes supported text captions to SRT. That SRT becomes the common timeline used by translation and, later, dubbing.

Image-only subtitle formats such as PGS are not silently OCR'd. Use local transcription for those.

### Local Whisper transcription

Open **Local transcription · Whisper** on Main.

Choose the Whisper model and spoken language, then click **Transcribe locally**.

Model installation/removal is intentionally not mixed into the processing screen. If the selected model is missing, go to:

**Settings → Model Manager → Whisper**

The current Whisper choices are:

| Model | Approximate size | Best use |
| --- | ---: | --- |
| Tiny | 75 MiB | quick tests / speed first |
| Base | 142 MiB | recommended starting point |
| Small | 466 MiB | better accuracy when extra time/storage is acceptable |

FFmpeg prepares 16 kHz mono audio and `whisper.cpp` creates the timestamped SRT locally. With **Auto detect**, Whisper's detected language is carried into translation where possible.

## 3. Translate locally

After extraction or transcription, open **Local translation** on Main.

Choose **Subtitle language** and **Translate to**, then click **Translate subtitles**.

The source language is normally filled from caption metadata or Whisper. If it is unknown, choose it manually.

Possible local routes include:

```text
English → Hungarian
Hungarian → English
Hungarian → English → German
```

The last route means that two non-English languages are translated locally through English.

If the required model is not installed, use **Settings → Model Manager → OPUS · subtitle translation**.

The output preview shows original and translated text side by side. Timestamps are preserved exactly, and **Translated SRT** gives you the translated file.

There is no silent cloud translation fallback.

# Settings

## Updates

Open **Settings → Updates**.

For a normal clean installation:

**Check for updates → Install update → Restart DubLocal**

The updater distinguishes the running DubLocal package, the local Git checkout, and official GitHub `main`.

Normal update rules are intentionally strict:

- only `ArrowSK/dublocal` `main` is trusted automatically;
- clean fast-forward updates are allowed;
- tracked local edits are never overwritten by a normal update;
- local commits or diverged history are not rewritten automatically.

### Repair installation

Use **Repair installation** when the checkout/runtime is inconsistent or tracked DubLocal program files were modified.

If tracked files need replacement, tick the repair confirmation first. DubLocal then saves a patch backup, restores official tracked files, refreshes the managed Python core, verifies the import/version, and schedules a clean restart.

Repair does **not** delete Whisper/translation models, the shared Hugging Face cache, generated jobs or untracked user files.

## Model Manager

Open **Settings → Model Manager** to install, verify or remove optional AI models.

This is the answer to the common question: **“How do I install the translation model?”**

### Whisper

Choose Tiny, Base or Small and click **Install / verify model**. DubLocal downloads only the requested model and verifies its checksum.

### OPUS translation

Choose the model set that matches the kind of translation you need:

| Model set | What it enables | Approximate weights |
| --- | --- | ---: |
| English → supported languages | English subtitles into Hungarian/German/etc. | 310 MiB |
| Supported languages → English | Hungarian/German/etc. into English | 310 MiB |
| Non-English ↔ non-English | both directions through an English pivot | 620 MiB total |

Then click **Install / verify required model(s)**.

DubLocal follows a **reuse first, install second** policy:

- if a compatible translation Python runtime already exists locally, it can be used through an isolated worker process;
- OPUS snapshots use the normal Hugging Face cache;
- if the exact pinned snapshot is already present, DubLocal registers/reuses it rather than storing another copy;
- only missing resources are obtained.

The current OPUS models are Apache-2.0. Exact revisions and SHA-256 values are recorded in `MODEL_LICENSES.json`.

Removing DubLocal's translation models removes its registration/private legacy copy but deliberately does not erase an underlying shared Hugging Face cache snapshot another application may still use.

### Kokoro

Kokoro voice generation arrives in M4. The Model Manager already reserves a Kokoro section, while **Local Resources** detects compatible existing installations so M4 can reuse one instead of installing a second copy.

## Local Resources

Open **Settings → Local Resources** to see what DubLocal can safely reuse on the Mac.

The panel currently reports:

- FFmpeg and ffprobe;
- `whisper-cli`;
- the shared Hugging Face cache location;
- compatible external Python runtimes such as an existing Kokoro environment.

Python virtual environments stay isolated. DubLocal never appends another application's `site-packages` into its own interpreter. Supported cross-application reuse happens through a small separate-process worker.

# YouTube HTTP 429

YouTube can temporarily rate-limit caption or media delivery. DubLocal retries ordinary caption delivery but does not try to evade the restriction.

If captions remain blocked, use **Transcribe locally**. If YouTube also refuses audio delivery, wait and retry later or use a local copy you are allowed to process.

# What M3 does not do yet

M3 stops at synchronized source and translated subtitle files.

M4 adds local Kokoro voice generation. M5 adds voice timing/audio mixing and stream-copy media output, including the choice between making the DubLocal mix the primary audio track or adding it as a second selectable audio stream without unnecessarily re-encoding compatible video.

# If something goes wrong

Do not reinstall everything immediately. Read the nearest status panel first. DubLocal keeps source access, captions, Whisper, translation, dependency reuse, updater and launcher failures separate where possible.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for practical recovery steps.
