# DubLocal user guide

**Current development build: v0.5.0.dev0 — M5 Local Dubbed Media Export**

DubLocal is meant to feel like a small Mac utility, not an AI console. The normal workflow stays on **Main**. Updates, models and reusable local resources stay under **Settings**.

There is no packaged DMG/GitHub Release yet.

# Main

## 1 · Source

Choose **YouTube** or **Local file**, then click **Load source**.

The Source card remains visible and confirms what is loaded, for example:

`✓ Loaded · OK · YouTube · Title · 6:15 · 2 caption tracks`

For local media, DubLocal inspects streams with ffprobe. For YouTube, the initial load inspects metadata/captions without downloading the complete video.

## 2 · Subtitles

Subtitles are a complete output. Translation is optional.

Choose an existing text caption track and click **Use existing subtitles**, or use **Transcribe locally** with Whisper.

The persistent status shows completion and language when known, for example:

`✓ Transcribed · OK · 34 timed segments · en · SRT ready to download`

### Automatic language identification

When Whisper detects a supported language, DubLocal carries that language into **3 · Translate → From** automatically. Existing caption-track metadata is used the same way.

DubLocal accepts the common ISO codes and full language names returned by local tools. A newly loaded source clears the previous job's language state.

If the engine genuinely cannot determine the language, **From** remains Auto and translation asks you to choose the source language once rather than guessing.

### Download format

- **SRT** — default.
- **VTT** — web/video workflows.
- **TXT** — plain transcript.

Changing format reuses the current timeline; Whisper does not run again.

### Filenames

Files exposed for download use the source title/filename and language suffix instead of generic `captions.srt` names:

```text
My Movie.en.srt
My Movie.es.vtt
Interview.hu.txt
```

Translated SRTs use the target-language suffix, for example `My Movie.ru.srt`.

### Whisper models

- **Base · 142 MiB** — normal default.
- **Small · 466 MiB** — stronger but slower.
- **Accurate · Large v3 Turbo Q5 · 547 MiB** — recommended for difficult dialogue, songs, accents or noisy audio.

Install optional Whisper models under **Settings → Model Manager → Whisper**.

### Automatic YouTube captions

YouTube automatic captions may already contain recognition mistakes. A translator cannot reliably reconstruct what the speaker actually said if the source text itself is wrong.

If the Original column looks obviously damaged, transcribe from audio with Accurate Whisper before judging translation quality.

## 3 · Translate

The normal choice is:

**Recommended for this Mac · Lightweight / Balanced / Best quality**

DubLocal detects Mac architecture and memory locally and selects a conservative Qwen3/llama.cpp profile. Main does not expose a model matrix; details remain under **Translation engine details** and **Settings → Model Manager**.

Current defaults:

```text
Apple Silicon < 12 GB     Qwen3 4B · single pass · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · single pass · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · up to 24k input
Intel < 24 GB             Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context · single pass
```

The llama.cpp runtime context itself is reduced with the profile, not just the prompt length.

### What context now covers

Translation is instructed to treat adjacent subtitle fragments as continuous discourse and use programme/nearby context to resolve:

- pronouns and who is speaking to whom;
- grammatical gender only when context supports it;
- recurring names and terminology;
- idioms and phraseological expressions by meaning/register rather than word-for-word substitution;
- metaphors and imagery without flattening them into literal nonsense or inventing new imagery;
- recurring refrains/phrases consistently;
- slang, jokes and profanity at the source register.

If gender is genuinely ambiguous, DubLocal asks the model to prefer a natural construction that avoids inventing unsupported gender where the target language allows it.

On the Best-quality profile, a second senior review pass checks meaning, gender/reference, idiomatic phrasing, metaphors, grammar, continuity and register against the source/context.

### Structural protections

Standalone caption tags such as `[MUSIC]` bypass translation and are copied exactly. DubLocal also rejects broken subtitle IDs, timestamp shifts, runtime/prompt leakage and unexpected writing-system contamination before writing the translated SRT.

If the source text is damaged ASR, the translator is told to remain conservative rather than hallucinate the probable original line.

## 4 · Voice-over

Choose **Translated subtitles** or **Source subtitles**, then a supported Kokoro language/voice/speed and click **Generate voice track**.

### Bracketed cues are silent

Subtitle files keep accessibility cues such as:

```text
[MUSIC]
[APPLAUSE]
[LAUGHS] Hello.
```

Voice generation uses a temporary cleaned copy instead:

```text
Hello.
```

Tag-only rows produce no speech. The original SRT/VTT is never modified by this cleaning step.

M4 still produces a voice-only WAV and timing diagnostics; M5 consumes that manifest for final media output.

## 5 · Export — M5

After generating a voice track, open **5 · Export**.

Choose:

### Audio track

**Replace primary audio · default**

- DubLocal mixes the generated voice with the original primary soundtrack.
- The source soundtrack is ducked while DubLocal speech is present.
- The DubLocal mix becomes the primary/default audio stream.
- Additional original audio tracks are retained where possible.

**Add dubbed audio as second track**

- All original audio tracks remain unchanged.
- The DubLocal mixed soundtrack is appended as another selectable audio stream.
- The new track receives language/title metadata and is not forced to default.

### Container

**MKV · recommended** is the safest choice for preserving mixed video/audio/subtitle codecs and multiple tracks.

**MP4** is available when the source streams are compatible with MP4 remuxing. If they are not, DubLocal stops and recommends MKV rather than silently re-encoding the video.

### Timing fitting

M5 uses the per-segment Kokoro timing manifest.

For a line that is too long, DubLocal:

1. borrows real silence until the next spoken segment when available;
2. speeds only that voice segment when still needed, up to 1.25×;
3. never truncates spoken words;
4. reports any line that still exceeds the available timing window.

### Soundtrack mixing

The first M5 mix uses sidechain ducking: the original primary soundtrack becomes quieter while translated speech is active, then returns to normal between voice segments.

The dubbed mix is AAC 192 kbit/s stereo.

This is **not source separation**. Original dialogue may still be quietly audible underneath the dub. Future source-separation work can replace this mix stage without changing the rest of the pipeline.

### Video handling

Video is stream-copied whenever present and compatible. DubLocal does not re-encode video just because audio changed.

The output status explicitly says `video stream copied · no re-encoding` when that path was used.

### Output filename

Dubbed media is named predictably:

```text
My Movie.dub.es.mkv
Interview.dub.en-US.mp4
```

# Settings

## Updates

Use **Check for updates → Install update → Restart DubLocal**.

Normal updates require a clean official fast-forward. **Repair installation** can save a patch backup of modified tracked files, restore official source and refresh the managed Python environment while preserving models/caches/jobs/untracked files.

## Model Manager

### Whisper

Install only the speech-recognition models you need.

### Contextual translation

The accordion title reflects the current Mac recommendation. Preparing contextual translation installs/reuses llama.cpp and downloads only the Qwen model recommended for that hardware.

### Fast legacy OPUS

A smaller/faster sentence-level option. It remains explicit and is never used as a silent fallback from contextual translation.

### Kokoro

DubLocal reuses compatible external Kokoro runtimes through an isolated worker rather than merging Python environments.

## Local Resources

Shows reusable FFmpeg/ffprobe, whisper.cpp, llama.cpp, shared Hugging Face cache and compatible external Python runtimes.

# Temporary files

Working data lives under:

```text
~/Library/Caches/DubLocal/jobs/
```

This now includes temporary YouTube source media used by M5, transcription WAVs, working subtitles, llama-server logs, Kokoro segment WAVs, timing-fitted segments, dubbed mixes and remuxed output files.

Normal launch removes jobs older than 24 hours and caps the temporary cache at 4 GiB, oldest-first. Persistent AI model assets/shared Hugging Face cache are not deleted by this policy.

# Kokoro language coverage

Official Kokoro frontends exposed by DubLocal include American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Translation can support languages that Kokoro cannot voice. DubLocal does not silently pronounce an unsupported language with the wrong frontend.

# YouTube HTTP 429

DubLocal retries ordinary caption retrieval but does not evade YouTube rate limits. Local Whisper is the fallback when captions are unavailable. M5 YouTube export may also need to acquire the source media; if YouTube rate-limits that request, wait or use a local copy you are authorized to process.

# Quality expectations

DubLocal aims for strong practical local output, not an assertion of professional-human translation/dubbing quality.

Always separate these failure classes:

1. source recognition can be wrong;
2. translation can be semantically/stylistically wrong;
3. TTS can pronounce/style speech poorly;
4. timing/mixing can be technically imperfect even when the text is correct.

The pipeline keeps these layers separate so one can be improved without redesigning the others.

For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
