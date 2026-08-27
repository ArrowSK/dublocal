# DubLocal troubleshooting

**Applies to v0.5.1.dev0 — Voice Match + Export Refinement.**

Most DubLocal failures belong to one stage. Fix that stage rather than reinstalling the entire app or deleting models/caches blindly.

## DubLocal.app opens nothing

Use **Stop DubLocal.app**, reopen **DubLocal.app**, then choose **Stop All & Launch**.

Launcher log:

```text
~/.dublocal/logs/dublocal.log
```

If the managed environment itself is missing, rerun:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

## Where temporary files go

Temporary YouTube media, voice-analysis WAVs, Whisper WAVs, generated subtitles, llama-server logs, TTS segments, fitted voice tracks, dubbed mixes and remux outputs live under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes jobs older than 24 hours and caps this temporary cache at 4 GiB by removing the oldest jobs first. Persistent Whisper/Qwen/Kokoro assets and the shared Hugging Face cache are not part of that cleanup.

# Source / YouTube

## YouTube HTTP 429

YouTube is temporarily rate-limiting caption or media delivery. DubLocal retries ordinary retrieval but does not bypass the restriction.

If captions are blocked, use **Transcribe locally**. If YouTube also refuses media needed for transcription/export, wait and retry or use a local copy you have the right to process.

# Transcription

## FFmpeg / ffprobe / whisper.cpp missing

Check **Settings → Local Resources** first. The macOS installer can offer Homebrew packages for missing tools. Whisper weights are managed separately in **Settings → Model Manager → Whisper**.

## Transcription is slow or inaccurate

Base prioritizes practicality. Small is stronger but slower. **Accurate · Large v3 Turbo Q5** is the preferred local quality choice for songs, accents, noisy material or obviously damaged automatic captions.

## Auto-detected language did not populate Translate → From

After successful Auto transcription the status should show a concrete source language and **Translate → From** should update automatically.

If it remains Auto:

1. check whether Whisper actually reported a language;
2. choose `From` manually if the detector returned nothing usable;
3. restart after updating so the current UI adapter is loaded;
4. include the exact language/status line when reporting the bug.

Loading a new source intentionally clears the previous job's language state.

# Contextual translation

## Why does my Mac show Lightweight, Balanced or Best quality?

Current conservative profiles are:

```text
Apple Silicon < 12 GB     Qwen3 4B · review off · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · review off · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · 24k input cap
Intel < 24 GB             Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context
```

The recommendation scales actual llama.cpp context allocation too, not just prompt length.

## Translation gets gender, idiom or metaphor wrong

The contextual prompt/review explicitly checks gender/reference from surrounding context, idioms/phraseology by meaning/register and metaphor fidelity.

A local model can still fail. First verify that the source transcript actually contains the necessary information. If it does, keep the shortest reproducible source/context example; that is useful for regression tests.

DubLocal deliberately tells the model not to invent unsupported gender/reference or repair garbled ASR by hallucination.

## Translation contains wrong-script characters, runtime text or shifted IDs

That should be rejected before a translated SRT is written. v0.5.1 retains strict ID/timestamp validation, runtime/prompt leakage checks and wrong-script contamination checks.

If such output survives, report the smallest source/translation sample plus the running version.

# Voice-over / Kokoro

## Another app has Kokoro but DubLocal does not detect it

Use **Settings → Local Resources → Rescan local resources**. A reusable environment must expose Kokoro, NumPy, PyTorch and Hugging Face Hub.

DubLocal invokes that Python environment as an isolated worker; it never injects another application's `site-packages` into its own interpreter.

## Voice-over reads `[MUSIC]` or other bracketed cues

It should not. Tag-only cues are removed from a temporary TTS-only timeline; inline cues are stripped from the spoken text while the actual subtitle file is preserved.

Expected:

```text
[MUSIC]            subtitle kept; nothing spoken
[LAUGHS] Hello     subtitle kept; only “Hello” spoken
```

## Auto voice sounds like the wrong vocal range

**Auto · match original vocal range** is a lightweight acoustic heuristic, not diarization or speaker recognition.

DubLocal analyzes the original audio inside subtitle windows and chooses a lower/higher Kokoro preset where the selected language provides both. If the audio is dominated by music/noise, contains overlapping speakers, or the pitch estimate is inconclusive, the heuristic can choose imperfectly or fall back to the default voice.

Use a manual Kokoro voice when you want deterministic casting.

## Does mixed male/female-style material load two TTS models?

No. DubLocal keeps one Kokoro language pipeline/model loaded and changes voice presets per segment. The additional work is the lightweight local F0 analysis and different voice assets, not a second neural TTS model.

# Export

## Original dialogue/singing is still audible under the dub

v0.5.1 is substantially stronger than the first M5 mix: when a source subtitle timeline is available, DubLocal suppresses the original audio across the **entire source dialogue/singing window**, not only while generated TTS is non-silent. Nearby windows are merged to reduce pumping.

However, ordinary consumer media usually contains a married mix. Without a dialogue-free Music & Effects stem or source separation, DubLocal cannot perfectly remove only the original human voice while preserving music/effects at full level.

This remains suppression/ducking + overlay. If the original vocal is still too prominent, report the source type and a short timing example. Optional source separation remains future work rather than a hidden heavy dependency.

## Original music becomes too quiet between translated lines

Suppression follows source subtitle windows. If the source captions span long instrumental gaps, the timeline itself may be too broad. Inspect the source subtitle timing first; better timing produces better ducking.

## Both subtitles are not visible in VLC

When generated source and translated SRTs are available, v0.5.1 embeds both by default.

For MKV, VLC should show them as separate selectable subtitle tracks. Existing source subtitle streams may also be present.

For MP4, generated subtitles are packaged as `mov_text`. If one is missing, include the final export status, container, and whether the source/translated SRT files existed immediately before Export.

No DubLocal subtitle is burned into the video by default.

## What does Replace primary audio do?

DubLocal creates a mixed dubbed soundtrack, makes it the default/primary audio track and retains additional original audio tracks where possible.

## What does Add dubbed audio as second track do?

All original audio tracks remain untouched and the DubLocal mixed soundtrack is appended as another selectable track with language/title metadata.

## Is the video re-encoded?

### Local file

**Original / best available** is the default and uses `-c:v copy` whenever compatible. The video bitstream is not re-encoded merely because audio/subtitles changed.

Selecting a lower resolution is an explicit opt-in to H.264 VideoToolbox encoding. DubLocal does not silently downscale and does not upscale a lower-resolution source.

### YouTube

The selected quality acts as a maximum source height. DubLocal asks yt-dlp for the best source at or below that resolution, then stream-copies the chosen video during final remux.

## Why does 2160p/1440p/etc not upscale my local file?

Those options are quality ceilings, not forced output dimensions. If the local source is already below the selected height, DubLocal keeps the original video rather than wasting time and quality on an upscale.

## MP4 export says to use MKV

The requested stream combination cannot be packaged into MP4 without an unsupported/silent transcode. Choose **MKV · recommended** to preserve the stream-copy design.

## A dubbed line is too long

DubLocal first borrows available silence before the next spoken line, then uses FFmpeg `atempo` up to 1.25× if needed. It never intentionally cuts words. Residual overflows are reported.

# Filenames

User-facing subtitle files use source-derived names:

```text
Movie Name.en.srt
Movie Name.ru.srt
Track Title.es.vtt
```

Dubbed files use names such as:

```text
Movie Name.dub.ru.mkv
```

`und` means the language could not be determined reliably.

# Updates / repair

## Updater reports modified tracked files

Normal update refuses to overwrite them. Use **Repair installation** only when the edits are accidental or the installation needs recovery. DubLocal saves a patch backup before replacing tracked files.

Backups:

```text
~/.dublocal/repair-backups/
```

## Update installed but UI is old

Click **Restart DubLocal**. If necessary reopen the launcher and choose **Stop All & Launch**.

# Still stuck?

Provide:

- exact text from the nearest persistent DubLocal status box;
- running DubLocal version from Settings;
- source type (YouTube/local);
- action clicked immediately before the error;
- detected source language if transcription/translation is involved;
- selected voice mode/language if voice generation is involved;
- selected audio mode/container/video quality if export is involved;
- launcher log tail only for startup/launcher failures.

Do not post account cookies, authentication tokens, copyrighted media you cannot share, or private paths you do not want public.
