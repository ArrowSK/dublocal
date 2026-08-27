# DubLocal user guide

**Current development build: v0.5.1.dev0 — Voice Match + Export Refinement**

DubLocal is meant to feel like a small Mac utility, not an AI console. The normal workflow stays on **Main**. Updates, models and reusable local resources stay under **Settings**.

There is no packaged DMG/GitHub Release yet. Development builds update from official `main` inside the app.

# Main

## 1 · Source

Choose **YouTube** or **Local file**, then click **Load source**.

The Source card stays visible and confirms what is loaded, for example:

`✓ Loaded · OK · YouTube · Title · 6:15 · 2 caption tracks`

For a local file, DubLocal inspects the streams with ffprobe. For YouTube, the first load inspects metadata and captions without downloading the full video.

## 2 · Subtitles

Subtitles are a complete output. Translation is optional.

Choose an existing text subtitle/caption track and click **Use existing subtitles**, or open the Whisper section and click **Transcribe locally**.

The persistent status confirms the result, for example:

`✓ Transcribed · OK · 34 timed segments · en · SRT ready to download`

### Automatic language identification

When Whisper detects a supported language, DubLocal carries that language into **3 · Translate → From** automatically. Existing subtitle-track language metadata is used the same way.

DubLocal normalizes both ISO codes such as `en` and labels such as `English`. Loading a new source clears the previous job's remembered language.

If the language genuinely cannot be identified, DubLocal leaves **From** at Auto and asks you to choose it instead of guessing.

### Download format and filenames

SRT is the default. VTT and TXT are also available. Changing format reuses the existing timeline; transcription does not run again.

Files exposed for download use the loaded media title/filename and a language suffix:

```text
My Movie.en.srt
My Movie.es.vtt
Interview.hu.txt
```

Translated subtitles use the target language, for example `My Movie.ru.srt`.

### Whisper models

- **Base · 142 MiB** — normal default.
- **Small · 466 MiB** — stronger but slower.
- **Accurate · Large v3 Turbo Q5 · 547 MiB** — preferred for songs, accents, noisy material and obviously damaged automatic captions.

Install optional Whisper models under **Settings → Model Manager → Whisper**.

YouTube automatic captions are not ground truth. If the Original column already contains nonsense, improve the source transcript first rather than expecting the translator to reconstruct missing words.

## 3 · Translate

The normal choice is **Recommended for this Mac · Lightweight / Balanced / Best quality**.

DubLocal detects Mac architecture and memory locally and chooses a conservative Qwen3/llama.cpp profile. Model details stay collapsed so Main remains simple.

Current defaults:

```text
Apple Silicon < 12 GB     Qwen3 4B · single pass · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · single pass · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review on · up to 24k input
Intel < 24 GB             Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context · single pass
```

The llama.cpp runtime context itself is reduced with the profile, not only the prompt length.

Contextual translation uses nearby dialogue, sampled programme-wide context and recent accepted translations. The prompt/review explicitly checks:

- pronouns and who is speaking to whom;
- grammatical gender only where context supports it;
- recurring names and terminology;
- idioms and phraseological expressions by meaning/register, not word-for-word substitution;
- metaphors and imagery without flattening or inventing them;
- recurring phrases/refrains consistently;
- slang, jokes and profanity at the source register.

Standalone caption cues such as `[MUSIC]` bypass translation and remain unchanged. DubLocal also validates subtitle IDs/timestamps, runtime leakage and unexpected writing-system contamination before writing the translated SRT.

## 4 · Voice-over

Choose **Translated subtitles** or **Source subtitles**, then generate a Kokoro voice track.

### Automatic voice matching — default

The normal Voice selection is **Auto · match original vocal range**.

DubLocal performs a lightweight local acoustic analysis of the source audio inside subtitle windows. It estimates whether each segment sits in a lower or higher vocal range and chooses an appropriate Kokoro preset for that segment.

This is deliberately lightweight:

- no second TTS model is loaded;
- no diarization or source-separation model is downloaded;
- the same Kokoro language pipeline stays loaded while voice presets change;
- mixed lower/higher material can therefore use two contrasting voices without doubling TTS memory.

This is acoustic preset matching, not speaker identification and not an inference of anyone's gender identity. If two people overlap inside one subtitle line, that line still receives one TTS voice. Manual voice selection remains available.

### Bracketed cues are silent

Subtitle files keep accessibility cues such as:

```text
[MUSIC]
[APPLAUSE]
[LAUGHS] Hello.
```

Voice generation uses a temporary speech-only timeline. Tag-only rows produce no speech; `[LAUGHS] Hello.` speaks only `Hello.`. The actual subtitle file remains unchanged.

## 5 · Export

After generating the voice track, open **5 · Export**.

### Audio track

**Replace primary audio · default**

DubLocal creates a mixed dubbed soundtrack and makes it the primary/default audio stream. Additional original audio tracks are retained where possible.

**Add dubbed audio as second track**

All original audio tracks remain untouched and the DubLocal mix is appended as another selectable stream with language/title metadata.

### Stronger original-dialogue suppression

Professional dubbing normally uses a dialogue-free Music & Effects stem. Ordinary YouTube/local files usually contain a married mix, so DubLocal cannot perfectly remove only the original human voice without source separation.

v0.5.1 improves the practical fallback: the **source subtitle timeline** guides suppression. Original audio stays strongly reduced across each complete source dialogue/singing window, including gaps where the translated TTS line has already finished. Nearby windows are merged to reduce pumping.

This is stronger ducking/overlay, not a claim of professional M&E separation. The original dialogue may still be faintly audible in difficult mixes.

### Original + translated subtitles are embedded by default

When generated source and translated SRTs exist, both are packaged as selectable subtitle tracks. They are **not burned into the video**.

- MKV preserves source subtitle streams where possible and adds DubLocal's generated tracks.
- MP4 packages generated SRT tracks as `mov_text`.

Players such as VLC can enable/disable each subtitle track independently.

### Video quality

**Original / best available** is the default.

For YouTube you can choose a maximum quality: 2160p, 1440p, 1080p, 720p or 480p. DubLocal downloads the best source at or below that height and then stream-copies the selected video during final remux.

For local files, **Original** keeps the video bit-for-bit with stream-copy. Selecting a lower resolution is an explicit opt-in to H.264 VideoToolbox re-encoding. DubLocal does not upscale a lower-resolution source merely because you selected a higher option.

### Container

**MKV · recommended** is the safest choice for mixed video/audio/subtitle codecs and multiple tracks.

MP4 is available when the requested streams can be packaged compatibly. DubLocal does not silently start a long video transcode merely to satisfy MP4.

### Timing fitting

For a voice line that is too long, DubLocal:

1. borrows real silence before the next spoken line when available;
2. applies modest tempo increase only if needed, capped at 1.25×;
3. never truncates spoken words;
4. reports any line that still cannot fit safely.

### Output filename

Dubbed media is named predictably:

```text
My Movie.dub.es.mkv
Interview.dub.en-US.mp4
```

# Settings

## Updates

Use **Check for updates → Install update → Restart DubLocal**.

Normal updates require a clean fast-forward from official `ArrowSK/dublocal` `main`. **Repair installation** can save a patch backup of modified tracked files, restore official source and refresh the managed Python environment while preserving models, caches and jobs.

## Model Manager

**Whisper** — install only the transcription models you need.

**Contextual translation** — prepares the hardware-appropriate local Qwen model and llama.cpp runtime.

**Fast legacy OPUS** — smaller/faster sentence-level translation; never a silent fallback from contextual translation.

**Kokoro** — reuses compatible external Kokoro runtimes through an isolated worker rather than merging Python environments.

## Local Resources

Shows reusable FFmpeg/ffprobe, whisper.cpp, llama.cpp, shared Hugging Face cache and compatible external Python runtimes.

# Temporary files

Working data lives under:

```text
~/Library/Caches/DubLocal/jobs/
```

This includes temporary YouTube media, voice-analysis audio, transcription WAVs, working subtitles, llama-server logs, Kokoro segments, timing-fitted audio, dubbed mixes and remux outputs.

Normal launch removes jobs older than 24 hours and caps the temporary cache at 4 GiB, oldest-first. Persistent model assets/shared Hugging Face cache are not deleted by this policy.

# Quality expectations

DubLocal aims for strong practical local output, not a guarantee of professional-human translation/dubbing quality. Keep the pipeline layers separate when diagnosing quality:

1. source recognition can be wrong;
2. translation can be semantically/stylistically wrong;
3. TTS voice/style can be wrong;
4. timing/mixing can be technically imperfect even when the text is correct.

For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
