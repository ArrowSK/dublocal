<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal — local subtitles, translation and dubbing" width="150">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  <strong>Turn a video into subtitles, a translation and a local AI voice-over — without sending the media to a dubbing service.</strong>
</p>

<p align="center">
  <a href="https://github.com/ArrowSK/dublocal/releases/download/v0.6.0b6/DubLocal-0.6.0b6-macOS-unsigned.dmg"><img alt="Download DubLocal for macOS" src="https://img.shields.io/badge/Download-macOS%20Beta-111827?style=for-the-badge&logo=apple&logoColor=white"></a>
  <a href="https://github.com/ArrowSK/dublocal/releases/tag/v0.6.0b6"><img alt="View GitHub release" src="https://img.shields.io/badge/GitHub-v0.6.0b6-2f81f7?style=for-the-badge&logo=github&logoColor=white"></a>
</p>

<p align="center">
  <sub><strong>macOS 13+.</strong> Open the DMG, drag DubLocal to Applications, then use <em>Open Anyway</em> once if macOS blocks the unsigned beta.</sub>
</p>

<p align="center">
  <img alt="Version 0.6.0b6" src="https://img.shields.io/badge/version-0.6.0b6-4d8dff">
  <img alt="Apache 2.0" src="https://img.shields.io/badge/license-Apache--2.0-6c7a89">
  <img alt="Local first" src="https://img.shields.io/badge/processing-local--first-19b5a5">
  <img alt="No cloud dubbing" src="https://img.shields.io/badge/cloud%20dubbing-none-19b5a5">
  <a href="https://github.com/ArrowSK/dublocal/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/ArrowSK/dublocal/actions/workflows/ci.yml/badge.svg"></a>
</p>

DubLocal is a local-first macOS application for people who want to understand, translate or re-voice video without turning the job into a collection of command-line tools. Give it a YouTube link, local media file, or a supported authenticated lesson; choose what you want back; DubLocal builds the processing route and keeps the heavy work on your Mac.

> **Current state:** **v0.6.0b6** is the current packaged macOS beta. Beta 6 reduces avoidable contextual-translation work on highly fragmented captions while keeping the same Qwen model, prompt, subtitle-ID validation and recovery policy. It also retains beta 5's format-aware output profiles, beta 4's subtitle-capable FFmpeg handling and beta 3's adaptive translation safety. The DMG remains intentionally unsigned and not notarized. Models remain optional downloads, finished outputs stay ordinary user files, and the packaged app keeps the existing safe in-app updater instead of introducing a second update system.

## Install on macOS

Use the **Download** button above or open the [v0.6.0b6 release](https://github.com/ArrowSK/dublocal/releases/tag/v0.6.0b6).

1. Download `DubLocal-0.6.0b6-macOS-unsigned.dmg`.
2. Open the DMG and drag **DubLocal.app** to **Applications**.
3. Control-click/right-click **DubLocal.app** and choose **Open** the first time.
4. If macOS still blocks it, go to **System Settings → Privacy & Security → Open Anyway**.
5. Let first-run setup finish. DubLocal prepares its private local environment and opens in your browser.

Do not disable Gatekeeper globally. The extra first-launch step exists only because this beta does not yet carry an Apple Developer ID signature.

The first setup needs an internet connection for the application environment and any optional components you choose. Large AI models are **not** bundled into the DMG.

For the slightly longer version, including uninstall and first-run requirements, see **[Beta installation](docs/BETA_INSTALLATION.md)**.

## The normal workflow

For most jobs, open **Main → Standard**.

```text
YouTube / local file / course lesson
                ↓
       choose output language
                ↓
  subtitles · translation · voice-over
                ↓
        optional finished media
```

The **Standard workflow** is deliberately compact. You choose the source, confirm you have legitimate access and the right or legal authority to process it, select an output language and choose the outputs you want. DubLocal resolves the required intermediate steps itself.

A typical complete job is simply:

1. choose **YouTube**, **Local file**, or **Course / Website**;
2. choose the target language;
3. leave **Subtitles**, **Translate**, **Voice-over** and **Media file** selected;
4. click **Start Processing**.

The queue is sequential, so a laptop is not asked to run several large speech/translation jobs at the same time.

## What DubLocal can do today

| Area | What you get |
| --- | --- |
| Sources | YouTube videos/playlists/channels, local audio/video, supported authenticated non-DRM course lessons |
| Subtitles | Existing text captions or local `whisper.cpp` transcription; SRT/VTT/TXT output |
| Translation | Local contextual Qwen3 translation with hardware-aware context, fragmentation-aware adaptive batching, prompt reuse where supported and strict subtitle alignment recovery |
| Voice-over | Kokoro and vetted local-language providers with automatic vocal-range matching where supported |
| Audio | Lightweight dialogue mixing everywhere; optional local Demucs separation for music-heavy material |
| Export | MKV, MP4 and Shareable MP4 with format-aware Auto/Original/High/Balanced/Compact output profiles, selectable or burned subtitles and selectable audio tracks |
| Queueing | Multiple local files, YouTube collections and course lessons processed one at a time |
| Storage | Automatic stale-job housekeeping plus **Settings → Storage & Cleanup** |
| Updates | In-app update from official `main` with guarded restart/repair behavior |

## Standard when you want it, Advanced when you need it

**Standard** is the normal consumer workflow. Optional controls sit under **Options**, so the main path does not require understanding the whole processing pipeline before getting a result.

**Advanced** exposes the same engines stage by stage:

**Source → Subtitles → Translate → Voice-over → Export**

Use Advanced when you want to inspect subtitle tracks, force local transcription, choose a particular model or voice, review intermediate text, or control export details manually. It is not a second implementation; it is a more explicit view of the same processing path.

## A few useful design choices

### Output profiles are format-aware

Open **Settings → Output profiles** to choose a persistent profile separately for **MKV**, **MP4** and **Shareable MP4**. Each can use **Auto**, **Original**, **High**, **Balanced** or **Compact**.

Auto intentionally means different things for different jobs:

- **MKV Auto → Original**: preserve the source video whenever practical.
- **MP4 Auto → Balanced**: compatible H.264-oriented output up to 1080p, re-encoding when the source is incompatible or materially larger than the target.
- **Shareable MP4 Auto → Compact**: up to 720p with a sharing-oriented bitrate; burned subtitles use the same profile.

The Standard workflow still exposes an optional **Resolution limit** under Options. That is an additional ceiling, not a second compression policy.

At 480p, Shareable Auto targets roughly **500 kbps video + 96 kbps audio**, or about **4.5 MB per minute**. The earlier quality-first export used 2.5 Mbps video + 192 kbps audio at 480p, which could make a short clip unexpectedly exceed 100 MB.

### DubLocal does not silently download large models

If a required local model is missing, the app tells you what to prepare in **Settings → Model Manager**. A normal subtitle job should not suddenly begin a multi-gigabyte download without asking.

### “Auto” tries to make a sensible decision

For subtitles, the recommended route generally prefers good creator/embedded text, but it can prefer an already-installed stronger local Whisper model over poor automatic captions. Detected transcription language is carried into contextual translation when possible.

For media output, Auto is format-aware rather than a single global quality setting. It also avoids a needless re-encode when an existing compatible stream already fits the selected target.

### Translation adapts for both safety and processing cost

Contextual Qwen translation keeps programme-wide, nearby and previously approved translation context while every generated subtitle still has to preserve its ID and pass target-language validation.

Normal sentence-sized subtitles keep the established optimistic limits of up to **48 lines on Qwen3 8B** and **36 on 4B**. Beta 6 recognizes unusually dense timelines made of very short caption fragments and can start those sections at up to **96/72 lines** instead. If an attempt does not align cleanly, only that section is retried at half size until the established **12-line safety floor** and bounded recovery path take over.

For short programmes, the llama.cpp runtime also allocates context from the programme budget the prompt can actually use instead of reserving a much larger KV cache merely because the hardware recommendation permits it. Current llama.cpp builds can additionally use conservative exact prompt-chunk reuse when the installed server exposes that capability; older builds simply keep the established command.

These changes do not select a smaller translation model or skip validation/review for speed. DubLocal still refuses to write an SRT when alignment cannot be established without guessing.

### Burned subtitles use an FFmpeg build that can actually render them

Normal media work can use the regular FFmpeg installation. Burned Shareable MP4 output additionally needs FFmpeg's libass-backed `subtitles` filter. DubLocal checks this before starting the encode and can use a side-by-side Homebrew `ffmpeg-full` build when the normal binary lacks the filter. It no longer retries an H.264 encoder when the real problem is a missing video filter.

### Original media is preserved where practical

MKV Auto and the explicit **Original** profile keep the source video stream without unnecessary recoding when possible. An explicit lower Resolution limit still wins when you actually want a smaller frame size.

### MKV is the comfortable default for multi-track output

DubLocal can keep original audio, add a dubbed track and retain selectable subtitle streams. MKV handles that combination more naturally than MP4, so it is the recommended container for full multi-track jobs.

### Authenticated websites are treated as sources, not a bypass system

DubLocal can open a dedicated local Chromium profile for supported sites. You sign in directly on the site; DubLocal does not ask for the password. Ordinary authorised non-DRM lesson media can then enter the normal local pipeline. Protected DRM/encrypted streams are refused rather than circumvented.

See **[Authenticated websites](docs/AUTHENTICATED_WEBSITES.md)** for the exact boundary.

## Local-first means the processing stays local

Speech recognition, translation, TTS and media processing are designed to run locally once their required models/runtime assets are installed. DubLocal does not require a cloud dubbing service for the pipeline itself.

Network access is still used where it is naturally required: downloading a YouTube source, obtaining optional models/runtimes, checking GitHub for updates, or signing into an authenticated source website.

Temporary working files live under:

```text
~/Library/Caches/DubLocal/jobs/
```

DubLocal prunes stale/oversized work automatically. Models, authenticated sessions and finished outputs are treated as persistent data and are protected from **Clean temporary files**.

## Output stays understandable

Finished files use the source title and target language rather than internal job IDs, for example:

```text
Movie Name.en.srt
Movie Name.es.srt
Movie Name.dub.es.mkv
Movie Name.subtitles.es.mkv
```

Course material is grouped by provider/course and keeps lesson order:

```text
~/Movies/DubLocal/Domestika/French Watercolour/
  01 - Introduction.fr.srt
  01 - Introduction.en.srt
  01 - Introduction.dub.en.mkv
```

Internal work files remain disposable cache data instead of appearing beside every finished export.

## Start here

If you want to **use DubLocal**, download the beta at the top of this page and then read the **[User Guide](docs/USER_GUIDE.md)** only when you need more than the Standard workflow.

If something goes wrong, start with **[Troubleshooting](docs/TROUBLESHOOTING.md)** rather than deleting caches or reinstalling models at random.

If you want to understand how the project is built, use the **[Documentation hub](docs/README.md)** and continue into architecture/audio/model notes from there.

## Documentation

| Guide | What it is for |
| --- | --- |
| [Documentation hub](docs/README.md) | Friendly map of the user, setup and developer documentation |
| [Beta installation](docs/BETA_INSTALLATION.md) | DMG install, first launch, Gatekeeper, updates and uninstall |
| [User Guide](docs/USER_GUIDE.md) | Standard workflow, Advanced mode, models, sources, outputs and day-to-day use |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Start here when a launch, model, source, transcription, voice or export step fails |
| [Storage & Cleanup](docs/STORAGE_CLEANUP.md) | What DubLocal stores and what automatic/manual cleanup may delete |
| [Authenticated websites](docs/AUTHENTICATED_WEBSITES.md) | Local sign-in sessions, course acquisition and DRM boundary |
| [TTS providers](docs/TTS_PROVIDERS.md) | Voice providers, language coverage and custom-provider rules |
| [Architecture](docs/ARCHITECTURE.md) | Main modules, trust boundaries and processing pipeline |
| [Audio architecture](docs/AUDIO_ARCHITECTURE.md) | Mixing, timing and optional source separation |
| [Production readiness](docs/PRODUCTION_READINESS.md) | Current hardening/validation status |

## Building from source

For development rather than normal installation:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The source installer creates launchers under `~/Applications`. The packaged beta instead owns a managed checkout under `~/Library/Application Support/DubLocal/app`, which lets the same guarded updater keep the installed beta current.

See **[Installation from source](docs/INSTALLATION.md)** for the development path.

## Licence

DubLocal application code is licensed under **Apache-2.0**. AI models, model weights and third-party runtime components may carry separate licences; see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and [MODEL_LICENSES.json](MODEL_LICENSES.json).
