# DubLocal user guide

**Current development build: v0.6.0.dev0 — Magic Flow UX**

DubLocal has three practical levels of control:

1. **Magic Flow** — the normal consumer workflow.
2. **More options** — medium complexity without exposing the full pipeline.
3. **Detailed workflow** — stage-by-stage control for difficult jobs and debugging.

Settings remains separate for updates, model management and local resources.

# Magic Flow — recommended

Magic Flow sits at the top of Main.

## Step 1 · Source

Choose **YouTube** or **Local file**.

- YouTube: paste the URL.
- Local: choose the media file.

## Step 2 · Rights

Tick:

**I have the right or legal authority to process this media**

DubLocal will not start the processing pipeline without this confirmation.

## Step 3 · Output language

Choose the language you want to receive.

This is the target for translation and, when supported by Kokoro, voice-over.

## Step 4 · Choose outputs

Magic Flow exposes four simple checkboxes:

- **Subtitles**
- **Translate**
- **Voice-over**
- **Output media file**

All are selected by default for a complete dubbed output.

You do not have to understand pipeline dependencies. For example, if Voice-over is selected, DubLocal automatically obtains a subtitle timeline and translation first.

## Step 5 · Run

Click **Run Magic Flow**.

The persistent status shows the route DubLocal selected, progress/ETA where measurable, and the detected source language. Finished files appear in the Results section.

# How Magic Flow chooses subtitles

With **Subtitle source → Auto choose · recommended**, DubLocal prefers:

1. creator/embedded text subtitles;
2. an already-installed **Accurate · Large v3 Turbo Q5** Whisper model;
3. an existing automatic caption track;
4. another already-installed local Whisper model.

The reasoning is practical: good supplied text is normally preferable to ASR, but if the stronger local music/difficult-audio model is already present, it can be preferable to poor automatic captions.

Magic Flow never silently downloads a large model. If no safe route is ready, it asks you to prepare one under **Settings → Model Manager**.

# More options — medium complexity

Open the collapsed **More options** section when you want more control without using the detailed pipeline.

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

## Video quality

- Original / best available — default.
- 2160p max
- 1440p max
- 1080p max
- 720p max
- 480p max

For a local file, Original means video stream-copy: no recoding merely because subtitles/audio changed.

For YouTube, a lower quality acts as a source-resolution ceiling before download.

# Detailed workflow — advanced control

The complete workflow remains below Magic Flow:

**1 Source → 2 Subtitles → 3 Translate → 4 Voice-over → 5 Export**

Use it when you need to inspect or override decisions. The individual stages remain collapsible.

## 1 · Source

Choose YouTube or Local file and click **Load source**.

A persistent card confirms title, duration and useful subtitle inventory.

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

**Auto · match original vocal range** performs lightweight acoustic analysis and can switch between lower/higher Kokoro voice presets per subtitle segment.

It does not load two TTS models. One Kokoro pipeline stays loaded while voice presets change.

This is acoustic range matching, not speaker identification or a claim about identity/gender.

### Caption tags are silent

The actual subtitle file remains intact, but the temporary TTS timeline removes non-dialogue cues:

```text
[MUSIC]          → no speech
[LAUGHS] Hello   → speaks “Hello”
```

## 5 · Export

### Replace primary audio

Creates the DubLocal mix as the default audio stream. Additional original streams are retained where possible.

### Add dubbed audio as second track

Keeps original audio streams untouched and adds DubLocal as another selectable stream.

### Package original + subtitles · no dub

Use this when you want the original media with source/transcribed subtitles but no translation/dub audio.

### Subtitle tracks

Normal dubbed export includes generated original + translated subtitles as selectable tracks when both are available. Nothing is burned into the video.

### Timing

Each generated speech segment targets its own subtitle timing window. DubLocal measures the generated WAV and can chain FFmpeg `atempo` stages over an effective 0.30×–2.50× range, followed by a small correction pass when necessary.

The subtitle timestamps themselves are not rewritten.

### Soundtrack level

The original programme is kept at a stable reduced bed rather than jumping back to full volume between dub lines. It is attenuated further inside source subtitle dialogue/singing windows, followed by gentle compression/limiting.

This is lightweight DSP. DubLocal does not claim to produce a true dialogue-free M&E stem from a married consumer soundtrack.

# Output names

DubLocal uses the source title/filename rather than generic `captions.srt` where user-facing output is concerned:

```text
Movie Name.en.srt
Movie Name.es.srt
Movie Name.dub.es.mkv
Movie Name.subtitles.es.mkv
```

# Settings

## Updates

Check, install and restart into newer official `main` revisions. Repair can restore a locally modified/broken checkout without requiring a manual reinstall.

## Model Manager

Install/remove/verify optional Whisper and contextual-translation models and prepare Kokoro.

## Local Resources

Shows reused FFmpeg/ffprobe, whisper.cpp, Hugging Face cache and compatible external runtimes.

# Temporary files

Working artifacts are kept under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes stale jobs and enforces the temporary cache cap. Model assets are persistent resources and are not removed by job cleanup.
