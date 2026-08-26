# DubLocal user guide

DubLocal is meant to be used like a small Mac utility, not like a Python project. Once it is installed, start it with **DubLocal.app** and work in the browser window it opens locally.

This guide describes the current M3 build: existing subtitles, local Whisper transcription and local subtitle translation.

## Before you start

DubLocal does not upload a local movie or audio file to a cloud AI service. Transcription and translation run locally on the Mac.

YouTube is different because the source itself is remote: DubLocal has to contact YouTube to inspect the video, request captions, or fetch audio when you explicitly ask for local transcription. You must have the right or legal authority to process the media.

## 1. Choose your source

At the top of DubLocal choose either **YouTube** or **Local file**.

For YouTube, paste one video URL and click **Scan source**. DubLocal shows the video title and any creator or automatic caption tracks it can discover.

For a local file, select your video or audio file and click **Scan source**. DubLocal uses `ffprobe` locally to inspect its streams and lists any embedded subtitle tracks.

## 2. Get timed source subtitles

There are two ways to continue.

### Use subtitles that already exist

Choose the subtitle/caption track you want, confirm that you have the right to process the media, then click **Extract existing subtitles**.

DubLocal converts supported text captions to a normalized SRT file. That normalized SRT is the common input used by later translation and dubbing stages.

Image-only subtitles such as PGS cannot be treated as text. For those, use local transcription instead.

### Create subtitles with Whisper

Open **Local transcription · Whisper**.

The status box tells you whether the `whisper.cpp` engine is ready and which models are installed. The current options are:

| Model | Approximate size | Good for |
| --- | ---: | --- |
| Tiny | 75 MiB | quick tests and speed-first work |
| Base | 142 MiB | recommended starting point |
| Small | 466 MiB | better accuracy when the extra time/storage is worthwhile |

If your chosen model is not installed, click **Install / verify model**. The model is downloaded only because you asked for it and is checksum-verified before use.

Choose the spoken language or leave **Auto detect**, then click **Transcribe locally**. DubLocal prepares 16 kHz mono audio with FFmpeg and runs whisper.cpp locally. The result is an SRT plus a timed preview.

When Auto detect is used, DubLocal also reads Whisper's detected language and carries it into the translation section when possible.

## 3. Translate the subtitles locally

Once you have an extracted or transcribed SRT, open **Local translation**.

The **Subtitle language** field should usually be filled automatically from the selected caption track or Whisper's detected language. If it says **Auto detect** or is wrong, choose the correct language manually. Translation deliberately does not guess an unknown subtitle language.

Choose **Translate to**.

The status panel shows the route DubLocal will use:

```text
English → Hungarian
Hungarian → English
Hungarian → English → German
```

The middle form means DubLocal uses English as a local pivot for a translation between two non-English languages.

### The first time a route is used

Click **Prepare translation**.

DubLocal then installs the optional local translation Python runtime into its own environment and downloads only the model or models needed for the selected route. The two current models are Apache-2.0 Helsinki-NLP OPUS models, each with roughly 310 MiB of weights.

English ↔ another supported language needs one model. A non-English ↔ non-English route needs both models.

The model downloads are pinned to exact upstream revisions and the safetensors weight file is SHA-256 verified. If verification fails, DubLocal deletes the failed download instead of using it.

### Translate

Click **Translate subtitles**.

DubLocal translates each timed segment locally. The original start and end times are not changed. The result panel shows the original text beside its translation, and **Translated SRT** gives you the new subtitle file.

Translation can use Apple Metal acceleration through PyTorch when the required operations are supported. If that path hits an unsupported MPS operation, DubLocal falls back to CPU for reliability.

There is no cloud translation fallback.

### Removing translation models

**Remove translation models** removes the downloaded OPUS model folders. It keeps the optional Python translation packages so that a later model reinstall is quicker and less disruptive.

## What if YouTube says HTTP 429?

YouTube occasionally rate-limits caption delivery. DubLocal retries the caption request, but it does not try to defeat the restriction.

If captions remain blocked, use **Transcribe locally**. DubLocal will request the video's audio only when you explicitly start that fallback. If YouTube is also rate-limiting media delivery, wait and retry later or use a local copy that you are allowed to process.

## Updating DubLocal

Open **DubLocal updates** and use:

**Check for updates → Install update → Restart DubLocal**

The updater contacts the configured GitHub remote only when you ask. It accepts only a safe fast-forward update and refuses to overwrite local changes.

If you have just installed an update that adds new optional dependencies, the updater refreshes DubLocal's core environment. Optional model/runtime packages remain opt-in through their own panels.

## What M3 does not do yet

M3 stops after producing synchronized source and translated subtitle files. It does not yet create spoken translated audio.

The next milestone is the local Kokoro TTS backend. Later stages will fit generated speech to subtitle timing, duck the original audio during translated speech and render a preview/final video.

## A useful rule when something goes wrong

Do not reinstall everything immediately. Read the status box first. DubLocal tries to separate failures by layer: source access, captions, Whisper engine/model, translation engine/model, updater, and launcher.

The practical fixes are collected in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
