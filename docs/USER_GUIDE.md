# DubLocal user guide

**Current beta: v0.6.0b1 — first packaged macOS beta**

For the unsigned DMG installation and one-time Gatekeeper steps, see `BETA_INSTALLATION.md`.

DubLocal keeps the normal experience and the full manual toolset separate.

Under **Main** there are two modes:

1. **Simple** — the default for normal use. It contains Magic Flow only.
2. **Advanced** — the complete stage-by-stage workflow for difficult jobs, overrides and debugging.

Settings remains separate for updates, model management, authenticated websites, storage/cleanup and local resources.

# Simple — recommended

Open **Main → Simple**. This is the normal consumer workflow.

Magic Flow asks only for the source, rights confirmation, output language and desired result. DubLocal chooses the local processing route itself. Additional controls remain under the collapsed **More options** section.

## Step 1 · Source

Choose **YouTube**, **Local file**, or **Course / Website**.

- YouTube: paste a video, playlist, or channel URL.
- Local: choose one or more media files.
- Course / Website: paste a legitimately accessible course/lesson URL, sign in through DubLocal's dedicated local browser when required, inspect the lessons, then select the ones to process.

Course / Website is an acquisition source only. Once a lesson is acquired as ordinary authorised non-DRM media, it enters the same Magic Flow pipeline as a local file.

## Step 2 · Rights

Tick the confirmation that you have legitimate access and the right/legal authority to process the content for your intended use.

DubLocal will not start the processing pipeline without this confirmation.

## Step 3 · Output language

Choose the language you want to receive.

This is the target for translation and, when a compatible provider exists, voice-over.

## Step 4 · Choose outputs

Magic Flow exposes four simple choices:

- **Subtitles**
- **Translate**
- **Voice-over**
- **Media file**

All are selected by default for a complete dubbed output.

You do not have to understand pipeline dependencies. For example, if Voice-over is selected, DubLocal automatically obtains a subtitle timeline and translation first.

## Step 5 · Run

Click **Run Magic Flow**.

The persistent status shows the route DubLocal selected, progress/ETA where measurable, and the detected source language. Multi-file, YouTube collection and course jobs run sequentially rather than loading several heavy models/jobs in parallel.

The **Results** section stays collapsed while processing so there is one clear progress surface instead of several output widgets showing duplicate loading states. Open Results when you want the finished files.

# How Magic Flow chooses subtitles

With **Subtitle source → Auto choose · recommended**, DubLocal prefers:

1. creator/embedded text subtitles;
2. an already-installed **Accurate · Large v3 Turbo Q5** Whisper model;
3. an existing automatic caption track;
4. another already-installed local Whisper model.

The reasoning is practical: good supplied text is normally preferable to ASR, but if the stronger local music/difficult-audio model is already present, it can be preferable to poor automatic captions.

Magic Flow never silently downloads a large model. If no safe route is ready, it asks you to prepare one under **Settings → Model Manager**.

# More options — medium complexity

Open the collapsed **More options** section inside Simple when you want more control without switching to Advanced.

## Subtitle source

- **Auto choose · recommended** — normal choice.
- **Prefer an existing subtitle track** — avoid local ASR when possible.
- **Force local transcription** — ignore supplied captions and use an installed Whisper model.

## Keep original audio

**Keep original audio as a separate selectable track** is enabled by default for Magic Flow output media.

This gives you the DubLocal mix plus the untouched original audio as another player-selectable stream where the container supports it.

## Output format

- **MKV · recommended** — safest for multiple audio/subtitle tracks.
- **MP4** — available for compatible stream combinations.
- **Shareable MP4** where applicable — can explicitly burn the intended subtitle track for messaging-app compatibility.

## Video quality

- Original / best available — default.
- 2160p max
- 1440p max
- 1080p max
- 720p max
- 480p max

For a local/acquired file, Original means video stream-copy where the selected container permits it: no recoding merely because subtitles/audio changed.

For YouTube, a lower quality acts as a source-resolution ceiling before download.

# Course / Website details

DubLocal uses its own local Chromium profile for authenticated sites. You type credentials directly into the website; DubLocal does not ask for the password. Sessions remain local and can be cleared from **Settings → Authenticated Websites**.

Course jobs support lesson selection, sequential processing, per-lesson failure isolation and resume state. Completed lessons are not processed again when resuming the same course. Finished course outputs are organized under `~/Movies/DubLocal/<Provider>/<Course>/` by default.

Protected DRM/encrypted streams are refused rather than bypassed. If a platform provides a legitimate downloadable local copy, that local file can be processed normally.

# Advanced — manual control

Open **Main → Advanced** when you need to inspect or override individual stages.

The complete workflow is:

**1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export**

The individual stages remain collapsible. Advanced preserves the same processing engines as Simple.

## 1 · Source

Choose YouTube, Local file, or a direct Course / Website lesson and click **Load source**.

A persistent card confirms title, duration and useful subtitle inventory. Full course lesson selection belongs in Simple; Advanced accepts one direct authenticated lesson at a time so it does not duplicate the course queue manager.

YouTube inspection does not download the full video at this stage. Local files are inspected with ffprobe.

## 2 · Subtitles

Subtitles are a complete output. You never need to translate or dub just to get an SRT.

Use an existing text track or **Transcribe locally**. The result is immediately downloadable as SRT/VTT/TXT with a meaningful source-derived filename such as:

```text
My Movie.en.srt
Interview.hu.vtt
```

### Auto language handoff

If local Whisper runs with **Auto detect**, its detected language is retained as workflow state.

When **Translate → From = Auto** is still selected:

- the detected transcription language is consumed automatically when known;
- if it is not known, contextual Qwen can identify the dominant subtitle language itself before translation.

Loading another source clears the previous job's language state.

### Whisper choices

- **Base · 142 MiB** — practical normal model.
- **Small · 466 MiB** — stronger/slower option.
- **Accurate · Large v3 Turbo Q5 · 547 MiB** — preferred for songs, accents, difficult/noisy audio and poor automatic captions.

### Anti-ghosting and missed words

Whisper can either hallucinate text or miss difficult speech. DubLocal avoids globally increasing decoder eagerness because that would trade one failure for the other.

Current safeguards can:

- use Silero VAD for compatible ordinary-speech paths;
- disable rolling text context for the Accurate music profile;
- identify severe near-duplicate repetition storms;
- re-decode suspicious ranges independently;
- suppress a severe range if it remains untrustworthy;
- selectively recheck sparse lines and short internal gaps;
- accept recovery only when two no-context attempts agree closely;
- reject text that merely echoes neighbouring subtitles.

On low-memory Apple Silicon, extra recovery is deliberately capped. DubLocal prefers an uncertain gap to invented dialogue.

## 3 · Translate

The normal choice is **Recommended for this Mac**.

```text
Apple Silicon <12 GB      Qwen3 4B · single pass · 8k
Apple Silicon 12–23 GB    Qwen3 8B · single pass · 16k
Apple Silicon 24 GB+      Qwen3 8B · review · up to 24k
Intel <24 GB              Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context
```

The llama.cpp runtime allocation scales with the recommendation too, protecting unified memory on 8 GB M1-class machines.

Contextual translation uses nearby dialogue, broader programme context and prior accepted translations. Its prompt/review covers reference/gender where supported by evidence, idioms/phraseology by meaning and register, metaphors, recurring terminology, slang, jokes and profanity.

Standalone tags such as `[MUSIC]` stay unchanged. Translation output is checked for subtitle-ID/timestamp integrity, runtime leakage and wrong-script contamination.

## 4 · Voice-over

### Auto voice — default

**Auto · match original vocal range** performs lightweight acoustic analysis and can switch between lower/higher compatible voice presets per subtitle segment.

It does not load two TTS models. One provider pipeline stays loaded while compatible voice presets change.

This is acoustic range matching, not speaker identification or a claim about identity/gender.

### Caption tags are silent

The actual subtitle file remains intact, but the temporary TTS timeline removes non-dialogue cues:

```text
[MUSIC]          → no speech
[LAUGHS] Hello   → speaks “Hello”
```

### Timing

DubLocal fits speech timing during TTS generation rather than broadly stretching the finished waveform afterward.

For each spoken subtitle line, DubLocal generates a natural pilot, measures its real duration against the subtitle window, then regenerates materially mismatched lines with native speed control where supported. A limited correction pass can be used when needed. Extreme mismatch is reported rather than forcing severely robotic speech. Subtitle timestamps themselves are not rewritten.

## 5 · Export

### Replace primary audio

Creates the DubLocal mix as the default audio stream. Additional original streams are retained where possible.

### Add dubbed audio as second track

Keeps original audio streams untouched and adds DubLocal as another selectable stream.

### Package original + subtitles · no dub

Use this when you want the original media with source/transcribed subtitles but no translation/dub audio.

### Subtitle tracks

Normal dubbed export includes generated original + translated subtitles as selectable tracks when both are available. Shareable MP4 can optionally burn one subtitle track only when explicitly selected.

### Soundtrack level

The lightweight mixer keeps the original programme at a stable reduced bed and attenuates it further inside source subtitle dialogue/singing windows. Optional local Demucs vocal/accompaniment separation can be prepared for music-heavy material; failure falls back to the lightweight path rather than blocking the job.

# Output names

DubLocal uses the source title/filename rather than generic `captions.srt` where user-facing output is concerned:

```text
Movie Name.en.srt
Movie Name.es.srt
Movie Name.dub.es.mkv
Movie Name.subtitles.es.mkv
```

Course jobs also keep lesson ordering in their names.

# Settings

## Updates

In 0.6.0b1, **Update DubLocal** checks the official `main` checkout, installs safe fast-forwards/managed repairs, and schedules an automatic restart. Local commits, divergent Git history and unexpected upstreams remain protected.

## Model Manager

Install/remove/verify optional Whisper and contextual-translation models and prepare supported TTS providers.

## Authenticated Websites

Prepare the dedicated Chromium runtime and clear stored local website sessions.

## Storage & Cleanup

Shows temporary jobs, translation cache, models, runtimes, browser data, logs, resume data and finished-output usage. **Clean temporary files** cannot delete installed models, authenticated sessions or finished outputs.

## Local Resources

Shows reused FFmpeg/ffprobe, whisper.cpp, Hugging Face cache and compatible external runtimes.

# Beta app and first launch

The 0.6.0b1 DMG installs a normal **DubLocal.app** using the established logo. The browser UI now shows the same mark in the header so the Finder/Dock identity and the product surface are consistent.

The packaged app maintains its program checkout under:

```text
~/Library/Application Support/DubLocal/app
```

See `BETA_INSTALLATION.md` before deleting application-support data: models, sessions, caches and finished outputs have different retention/uninstall semantics.

# Temporary files

Working artifacts are kept under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes stale jobs and enforces the temporary cache cap. Model assets are persistent resources and are not removed by job cleanup.
