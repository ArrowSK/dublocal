<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, contextual translation, AI voice-over and track-aware media export for macOS.<br>
  Processing stays on your Mac.
</p>

<p align="center">
  <strong>Current development build: v0.6.0.dev0 · Magic Flow</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal turns a YouTube link or local media file into subtitles, translated subtitles, local AI voice-over, or a finished multi-track media file. It is designed to offer a simple consumer workflow without hiding the detailed controls needed for difficult material.

There is no packaged DMG/GitHub Release yet. Development builds update from official `main` inside DubLocal.

## Magic Flow — the normal way to use DubLocal

The top of **Main** is now a compact one-action workflow:

1. choose **YouTube** or **Local file**;
2. paste the link or select the file;
3. confirm that you have the right or legal authority to process it;
4. choose the **output language**;
5. tick what you want: **Subtitles**, **Translate**, **Voice-over**, **Output media file**;
6. click **Run Magic Flow**.

DubLocal resolves prerequisites automatically. For example, asking for a dubbed output also creates the subtitle timeline and translation needed to generate that dub.

### What “Auto choose” does

Magic Flow does not blindly pick the smallest or fastest route. It prefers, in order:

1. creator/embedded text subtitles when available;
2. an already-installed **Accurate · Large v3 Turbo Q5** local Whisper model;
3. existing automatic captions;
4. another already-installed local Whisper model.

It never silently downloads a large AI model. If no safe subtitle route is ready, Magic Flow tells you exactly what to prepare in **Settings → Model Manager**.

### More options — medium complexity

The default Magic Flow remains compact. Open **More options** only when needed:

- subtitle source: Auto / prefer existing / force local transcription;
- keep the original audio as a separate selectable track;
- output container: **MKV recommended** or MP4;
- video quality: Original/best, 2160p, 1440p, 1080p, 720p or 480p.

### Detailed workflow — advanced control

The original stage-by-stage workflow remains below Magic Flow:

**Source → Subtitles → Translate → Voice-over → Export**

Use it when you want to inspect tracks, choose a particular Whisper model, review translation output, choose voices manually, or control export details stage by stage. Its individual stages remain collapsible.

## What works now

| Stage | What DubLocal does |
| --- | --- |
| Source | YouTube URL or local video/audio; ffprobe/yt-dlp inspection |
| Subtitles | Existing text captions or local `whisper.cpp`; SRT/VTT/TXT download |
| Translation | Hardware-aware Qwen3 4B/8B contextual translation; optional legacy OPUS |
| Voice | Kokoro; caption cues stay silent; automatic lower/higher vocal-range matching |
| Timing | Per-line duration fit against subtitle start/end windows |
| Mixing | Stable reduced original bed + stronger dialogue/singing-window suppression |
| Export | Replace/add dub audio, subtitle-only package, selectable subtitle streams, video stream-copy by default |

## Auto language really means Auto

Local Whisper language detection is carried into translation. If **Translate → From = Auto** remains selected:

- DubLocal uses the language already detected by local transcription when available;
- otherwise contextual Qwen performs a lightweight subtitle-language identification inside the same runtime session before translating.

Legacy OPUS still requires a known source language because it has no equivalent contextual detector.

## Translation: Recommended for this Mac

DubLocal scales the local model and llama.cpp context allocation to the hardware:

| Mac class | Default profile |
| --- | --- |
| Apple Silicon <12 GB | Qwen3 4B · single pass · 8k input cap |
| Apple Silicon 12–23 GB | Qwen3 8B · single pass · 16k input cap |
| Apple Silicon 24 GB+ | Qwen3 8B · senior review · up to 24k |
| Intel <24 GB | Qwen3 4B · smaller context |
| Intel 24 GB+ | Qwen3 8B · single pass · reduced context |

An 8 GB M1 is therefore a supported design target, not an afterthought.

Contextual translation uses nearby dialogue, wider programme context and prior accepted translations. The prompt/review handles discourse reference and gender where the source supports it, idioms and phraseology by meaning/register, metaphors, recurring terminology, slang, jokes and profanity. Subtitle IDs/timestamps and output script are validated before an SRT is written.

Standalone tags such as `[MUSIC]` remain structural subtitle data. They are not translated as dialogue and are never read aloud.

## Transcription reliability

Whisper can fail in opposite directions: invent speech or miss real words. DubLocal deliberately does not solve one by globally loosening the decoder and reopening the other.

The current local path combines:

- optional Silero VAD for compatible ordinary-speech jobs;
- no rolling text context for the Accurate music profile;
- detection and isolated re-decoding of pathological repetition storms;
- suppression of severe unrecoverable ghost regions rather than trusting them;
- targeted rechecks of suspicious sparse/gap regions;
- acceptance only when two independent no-context retries agree closely;
- neighbour-echo rejection.

On Apple Silicon below 12 GiB, extra recovery is capped so this does not become a hidden second full-file transcription pass.

## Voice-over

**Auto · match original vocal range** is the normal choice. DubLocal analyses the source acoustically and can switch between lower/higher Kokoro voice presets per subtitle segment while keeping one Kokoro model/runtime loaded.

This is vocal-range matching, not speaker identity or gender-identity classification.

Caption cues remain useful in SRT/VTT but are removed from the temporary speech timeline:

```text
[MUSIC]          → silence
[LAUGHS] Hello   → speaks “Hello”
```

## Timing and soundtrack balance

Each generated line targets its own subtitle window. DubLocal measures the actual generated WAV and uses chained FFmpeg `atempo` stages for an effective **0.30×–2.50×** correction range, including a small correction pass when needed. Subtitle timestamps themselves are not rewritten.

Consumer media usually contains a married soundtrack rather than a dialogue-free M&E stem. DubLocal therefore uses lightweight DSP instead of pretending to perform perfect source separation:

- the original soundtrack stays at a stable reduced bed level;
- source dialogue/singing windows are attenuated further;
- gentle compression and limiting reduce distracting loudness jumps.

## Export modes

**Replace primary audio** creates a DubLocal mix as the default audio stream.

**Add dubbed audio as second track** keeps original audio streams untouched and appends DubLocal as another selectable stream.

**Package original + subtitles · no dub** keeps the original audio and adds the current source/transcribed subtitle without adding translated audio.

Magic Flow can also package original + translated subtitle tracks without a dub when translation and media output are selected but voice-over is not.

Nothing is burned into the picture. Generated subtitles remain selectable tracks in compatible players such as VLC.

## Video quality and recoding

**Original / best available** is the default.

For YouTube, a quality choice acts as a source-resolution ceiling before download; the final video is then stream-copied when compatible.

For local files, **Original** uses `-c:v copy`. Selecting a lower resolution explicitly opts into Apple VideoToolbox H.264 encoding. DubLocal does not silently re-encode local video merely because audio or subtitles changed.

**MKV is recommended** for multi-track output. MP4 is available for compatible stream combinations.

## Meaningful output names

User-facing outputs derive from the loaded title or filename, for example:

```text
Movie Name.en.srt
Movie Name.es.srt
Movie Name.dub.es.mkv
Movie Name.subtitles.es.mkv
```

Internal work files remain disposable cache artifacts rather than cluttering normal folders.

## Temporary data

Working jobs live under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes jobs older than 24 hours and caps temporary job data at 4 GiB. Persistent AI models and shared Hugging Face assets are not treated as temporary files.

## Install

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates native launchers under `~/Applications` and can repair the managed environment later from inside DubLocal.

See `docs/INSTALLATION.md`, `docs/USER_GUIDE.md`, `docs/ARCHITECTURE.md` and `docs/TROUBLESHOOTING.md` for details.
