# DubLocal user guide

**Current development build: v0.5.3.dev0 — M5 Stabilization**

DubLocal is designed to feel like a small Mac utility rather than an AI control panel. The normal workflow stays on **Main**; maintenance lives under **Settings**.

# Main

## 1 · Source

Choose **YouTube** or **Local file**, then click **Load source**.

A persistent card confirms readiness, for example:

`✓ Loaded · OK · YouTube · Title · 6:15 · 2 caption tracks`

YouTube inspection does not download the full video at this stage. Local files are inspected with ffprobe.

## 2 · Subtitles

Subtitles are a complete output. You never need to translate or dub just to get an SRT.

Use an existing text caption track or **Transcribe locally**. The result appears immediately as a downloadable SRT/VTT/TXT with a source-derived filename such as:

```text
My Movie.en.srt
Interview.hu.vtt
```

### Language detection

Whisper/track metadata is carried into **Translate → From** where possible. If **From = Auto** remains selected, contextual translation can identify the dominant subtitle language with the same local Qwen runtime before translating.

Loading a new source clears the previous job's language state.

### Whisper model choice

- **Base · 142 MiB** — practical normal default.
- **Small · 466 MiB** — stronger, slower.
- **Accurate · Large v3 Turbo Q5 · 547 MiB** — preferred for songs, accents, noisy audio and poor automatic captions.

### Anti-ghosting and missing words

Whisper can fail in opposite directions: invent speech or miss difficult words. v0.5.3 keeps the anti-hallucination policy conservative and adds targeted recovery rather than globally loosening the decoder.

DubLocal can:

- use Silero VAD for compatible ordinary-speech paths;
- disable rolling text context for the Accurate music profile so one bad lyric cannot seed a long repetition loop;
- detect severe near-duplicate subtitle storms and isolate/recheck them;
- suppress a severe range if an independent retry remains untrustworthy;
- selectively recheck sparse lines and short internal gaps;
- accept missing-word recovery only when **two isolated no-context passes agree closely**;
- reject candidates that merely repeat a neighbouring subtitle.

On Apple Silicon below 12 GiB, additional recovery is capped at 3 regions / 24 seconds. DubLocal prefers an uncertain gap over invented dialogue.

## 3 · Translate

The normal choice is **Recommended for this Mac**.

```text
Apple Silicon <12 GB      Qwen3 4B · single pass · 8k
Apple Silicon 12–23 GB    Qwen3 8B · single pass · 16k
Apple Silicon 24 GB+      Qwen3 8B · review · up to 24k
Intel <24 GB              Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context
```

The llama.cpp runtime allocation scales with the recommendation too; this prevents an 8 GB M1 from reserving an unnecessarily large KV cache.

Contextual translation uses neighbouring dialogue, programme-wide context and prior accepted translations. Its prompt/review specifically covers reference/gender when supported by context, idioms and phraseology by meaning/register, metaphors, recurring terminology, slang, jokes and profanity.

Standalone accessibility tags such as `[MUSIC]` remain unchanged. Translation output is checked for subtitle-ID/timestamp integrity, runtime leakage and wrong-script contamination.

## 4 · Voice-over

Choose Source or Translated subtitles and generate a Kokoro voice track.

### Auto voice — default

**Auto · match original vocal range** performs lightweight source-audio F0 analysis and chooses lower/higher Kokoro presets per subtitle segment.

It does not load two TTS models. One Kokoro pipeline remains loaded while voice presets change. This is acoustic range matching, not speaker identification or gender-identity classification.

### Caption tags are silent

The subtitle file remains intact, but the temporary TTS timeline removes cues:

```text
[MUSIC]          → no speech
[LAUGHS] Hello   → speaks “Hello”
```

## 5 · Export

### Replace primary audio — default

Creates the DubLocal mix as the default audio stream. Additional original audio tracks are retained where possible.

### Add dubbed audio as second track

Keeps original audio tracks untouched and adds DubLocal as another selectable stream.

### Package original + subtitles · no dub

Use this when you want a normal media file with subtitles but no translation/dub embedded.

This mode:

- keeps original audio untouched;
- embeds the current source/transcribed SRT as a selectable track;
- does not add the translated subtitle track;
- does not add a DubLocal audio track;
- keeps local Original video as stream-copy by default.

### Stable soundtrack loudness

A married consumer soundtrack cannot provide a perfect dialogue-free M&E stem. DubLocal therefore uses lightweight attenuation rather than claiming source separation.

v0.5.3 keeps the original programme at a stable reduced bed level across the dubbed output, then attenuates it further through source dialogue/singing subtitle windows. Gentle compression/limiting prevents the soundtrack from suddenly becoming extremely loud when a DubLocal line ends.

### Per-line timing

Every generated voice segment is measured against its subtitle window. DubLocal can chain legal FFmpeg `atempo` filters to achieve an effective **0.30×–2.50×** correction range. A second small correction pass handles duration rounding when the spoken end still misses the target by more than about 25 ms.

A small onset cushion remains so synthetic speech does not consistently jump in ahead of the source. Subtitle timestamps themselves are never moved.

Pathological stretches are reported rather than forced.

### Subtitle tracks

Normal dubbed exports embed generated original + translated SRTs as selectable tracks when both exist. They are not burned into the image.

MKV can also preserve source subtitle streams. MP4 converts generated SRT tracks to `mov_text` when compatible.

### Video quality

**Original / best available** is the default.

For YouTube, 2160p / 1440p / 1080p / 720p / 480p is a source-quality ceiling; the selected stream is then copied during final remux.

For local files, Original means `-c:v copy`. Choosing a lower resolution explicitly opts into H.264 VideoToolbox encoding. A higher option never forces an upscale.

**MKV · recommended** is the safest container for mixed codecs and multiple tracks.

# Settings

## Updates

Use **Check for updates → Install update → Restart DubLocal**. Updates require a clean fast-forward from official `main`.

**Repair installation** can save a patch backup, restore official tracked code and refresh the managed environment while preserving models/caches/jobs.

## Model Manager

- Whisper transcription models and auxiliary speech detector.
- Hardware-aware Qwen contextual translation.
- Optional small/fast legacy OPUS.
- Kokoro voice generation/reusable runtime.

## Local Resources

Shows reusable FFmpeg/ffprobe, whisper.cpp, llama.cpp, shared Hugging Face cache and compatible isolated Python runtimes.

# Temporary files

Working files live under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes jobs older than 24 hours and caps the cache at 4 GiB, oldest first. Persistent AI models/shared Hugging Face assets are excluded.

# Diagnosing quality

Keep the layers separate:

1. transcription may be wrong or incomplete;
2. translation may be semantically/stylistically wrong;
3. voice choice/style may be wrong;
4. timing/mixing can be wrong even when the text is correct.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for stage-specific checks.
