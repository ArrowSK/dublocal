<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, contextual translation, AI voice-over and track-aware media export for macOS.<br>
  Processing stays on your Mac.
</p>

<p align="center">
  <strong>Current beta: v0.6.0b1 · Magic Flow</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal turns a YouTube link, local media file, or legitimately accessible authenticated course/lesson into subtitles, translated subtitles, local AI voice-over, or a finished multi-track media file. It is designed to offer a simple consumer workflow without hiding the detailed controls needed for difficult material.

**0.6.0b1 is the first packaged macOS beta.** It is available as a conventional drag-to-Applications DMG with the DubLocal app icon and remains intentionally unsigned/not notarized for this first beta. The packaged app keeps a managed official Git checkout so the existing safe in-app updater and automatic restart path continue to work. See `docs/BETA_INSTALLATION.md` for first-launch Gatekeeper instructions and uninstall details.

## Magic Flow — the normal way to use DubLocal

The top of **Main** is now a compact one-action workflow:

1. choose **YouTube**, **Local file**, or **Course / Website**;
2. paste the link, select local files, or sign in and select course lessons;
3. confirm that you have legitimate access and the right or legal authority to process the media;
4. choose the **output language**;
5. tick what you want: **Subtitles**, **Translate**, **Voice-over**, **Output media file**;
6. click **Run Magic Flow**.

DubLocal resolves prerequisites automatically. For example, asking for a dubbed output also creates the subtitle timeline and translation needed to generate that dub.

### Course / Website sources

Authenticated courses are a source type, not a second dubbing pipeline. DubLocal opens a dedicated local Chromium profile for sign-in, discovers supported lessons, acquires ordinary authorised non-DRM media into the temporary job cache, and then hands that local media to the same Magic Flow used everywhere else.

The first adapter is **Domestika**, with a generic authenticated-video fallback for straightforward sites. Multi-lesson courses run sequentially, preserve successful outputs when one lesson fails, and persist a small resume manifest so completed lessons are not processed again after a restart.

DubLocal never asks for the website password and does not bypass DRM. Settings → **Authenticated Websites** prepares the optional browser runtime and clears local website sessions. See `docs/AUTHENTICATED_WEBSITES.md` for the security and provider architecture.

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
- output container: **MKV recommended**, ordinary MP4, or Shareable MP4 where applicable;
- video quality: Original/best, 2160p, 1440p, 1080p, 720p or 480p;
- compact audio/voice/sharing controls for single-voice and optional subtitle burn-in behavior.

### Detailed workflow — advanced control

The original stage-by-stage workflow remains below Magic Flow:

**Source → Subtitles → Translate → Voice-over → Export**

Use it when you want to inspect tracks, choose a particular Whisper model, review translation output, choose voices manually, or control export details stage by step. **Course / Website** is available there for a direct single-lesson URL; full course selection remains in Simple so the detailed pipeline is not duplicated.

## What works now

| Stage | What DubLocal does |
| --- | --- |
| Source | YouTube, local video/audio, or authenticated Course / Website; provider acquisition normalizes to local media |
| Subtitles | Existing text captions or local `whisper.cpp`; SRT/VTT/TXT download |
| Translation | Hardware-aware Qwen3 4B/8B contextual translation; optional legacy OPUS |
| Voice | Kokoro plus vetted local-language providers; caption cues stay silent; automatic lower/higher vocal-range matching |
| Timing | Native TTS speed adjustment only where a generated line genuinely overflows its subtitle window |
| Mixing | Lightweight dialogue mix everywhere; optional local Demucs vocal/accompaniment separation for music-heavy material |
| Export | Replace/add dub audio, subtitle-only package, selectable subtitle streams, stream-copy by default, optional shareable MP4 |

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
- targeted bounded rechecks of suspicious sparse/gap regions;
- agreement/recovery guards that reject neighbour echoes and low-confidence repairs.

On Apple Silicon below 12 GiB, extra recovery remains capped so this does not become a hidden second full-file transcription pass.

## Voice-over

**Auto · match original vocal range** is the normal choice. DubLocal analyses the source acoustically and can switch between lower/higher compatible voice presets per subtitle segment while keeping one TTS runtime loaded where the provider supports that behavior.

This is vocal-range matching, not speaker identity or gender-identity classification.

Caption cues remain useful in SRT/VTT but are removed from the temporary speech timeline:

```text
[MUSIC]          → silence
[LAUGHS] Hello   → speaks “Hello”
```

## Timing and soundtrack balance

Each generated line targets its own subtitle window. Native Kokoro timing treats that window as a maximum: a line that already fits keeps its selected natural speed; only genuine overflow is regenerated faster, with a bounded correction pass when useful. Subtitle timestamps themselves are not rewritten by TTS timing.

Consumer media usually contains a married soundtrack rather than a dialogue-free M&E stem. DubLocal therefore has two local paths:

- a lightweight mixer that remains the universal fallback and keeps a stable reduced programme bed with stronger suppression during dubbed dialogue/singing windows;
- optional local Demucs vocal/accompaniment separation for music-heavy material, with hardware-aware profiles and automatic fallback to the lightweight mixer if separation is unavailable or fails.

## Export modes

**Replace primary audio** creates a DubLocal mix as the default audio stream.

**Add dubbed audio as second track** keeps original audio streams untouched and appends DubLocal as another selectable stream.

**Package original + subtitles · no dub** keeps the original audio and adds the current source/transcribed subtitle without adding translated audio.

Magic Flow can also package original + translated subtitle tracks without a dub when translation and media output are selected but voice-over is not.

Generated subtitles remain selectable tracks by default in compatible players such as VLC. Shareable MP4 can optionally burn the intended subtitle track permanently into the picture for messaging-app compatibility; this is an explicit choice rather than the normal export behavior.

## Video quality and recoding

**Original / best available** is the default.

For YouTube, a quality choice acts as a source-resolution ceiling before download; the final video is then stream-copied when compatible.

For local and acquired authenticated media, **Original** keeps the source video without unnecessary re-encoding where the selected container permits it. Selecting a lower resolution explicitly opts into the established macOS encoding path.

**MKV is recommended** for multi-track output. MP4 and Shareable MP4 are available for their compatible stream combinations.

## Meaningful output names

User-facing outputs derive from the loaded title or filename, for example:

```text
Movie Name.en.srt
Movie Name.es.srt
Movie Name.dub.es.mkv
Movie Name.subtitles.es.mkv
```

Course outputs retain lesson order and are grouped by provider/course, for example:

```text
~/Movies/DubLocal/Domestika/French Watercolour/
  01 - Introduction.fr.srt
  01 - Introduction.en.srt
  01 - Introduction.dub.en.mkv
```

Internal work files remain disposable cache artifacts rather than cluttering normal folders.

## Temporary data

Working jobs, including temporary authenticated source media, live under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes stale/oversized job data according to DubLocal's cache policy. Persistent AI models, shared Hugging Face assets, authenticated browser profiles and small course-resume manifests are not treated as temporary job files.

## Install

For beta users, use the unsigned `DubLocal-0.6.0b1-macOS-unsigned.dmg`, drag **DubLocal.app** to Applications, then follow `docs/BETA_INSTALLATION.md` for the one-time Gatekeeper step. The app icon and in-app header use the same established DubLocal logo.

For development from source:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The source installer creates native launchers under `~/Applications`. The packaged beta instead keeps its managed checkout under `~/Library/Application Support/DubLocal/app` so the same updater can safely fast-forward official `main`.

See `docs/BETA_INSTALLATION.md`, `docs/INSTALLATION.md`, `docs/USER_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/AUTHENTICATED_WEBSITES.md` and `docs/TROUBLESHOOTING.md` for details.
