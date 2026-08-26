<p align="center">
  <img src="assets/macos/DubLocal.svg" width="150" alt="DubLocal logo">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  <strong>Local subtitles and voice-over tooling for macOS.</strong><br>
  Start with a YouTube link or a local media file. Use existing captions when they work; fall back to local speech transcription when they do not.
</p>

<p align="center">
  macOS 13+ · Apple Silicon + Intel · Python 3.11+ · Apache-2.0
</p>

---

## What DubLocal is

DubLocal is an open-source, local-first macOS app for building translated subtitle and dubbing workflows without sending your media to a cloud transcription service by default.

Today it can inspect media, discover or extract subtitles, and create timestamped subtitles locally with `whisper.cpp`. Translation and generated voice-over are the next layers of the same pipeline rather than separate throw-away tools.

The normal interface is a branded **DubLocal.app** launcher. Terminal is needed for the first installation only; after that the app can check for and install GitHub updates from inside DubLocal.

## What works today

| Area | Current support |
| --- | --- |
| YouTube | Scan one video, discover creator/automatic captions, extract captions when YouTube allows it |
| Local media | Inspect common video/audio containers with `ffprobe`; discover and extract text subtitle tracks |
| YouTube rate limits | HTTP 429 caption failures are handled cleanly and can fall back to local transcription |
| Local transcription | `whisper.cpp` / `whisper-cli`, timestamped SRT output, subtitle preview |
| Whisper models | Tiny, Base and Small; install/remove on demand; checksummed before use |
| Apple Silicon | Normal whisper.cpp Metal-accelerated path |
| Intel Macs | Conservative CPU compatibility path |
| Updates | Built-in GitHub update checker/installer with safe fast-forward-only updates |
| Launcher | `DubLocal.app` and `Stop DubLocal.app` with the branded icon |

Not implemented yet: translation, Kokoro voice generation, duration fitting, audio ducking and rendered dubbed-video export. The UI does not pretend those layers exist before they are real.

## Install once

Open Terminal and run:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates the local Python environment, checks the required media tools, can offer Homebrew installation of FFmpeg and `whisper.cpp`, generates the macOS icon, and installs:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

No Whisper model is downloaded automatically. Launch DubLocal, open **Local transcription · Whisper**, and install a model only when you want local transcription. **Base (142 MiB)** is the recommended starting point.

For a slower, explained walkthrough, see [Installation](docs/INSTALLATION.md).

## Your first subtitle

1. Open **DubLocal.app**.
2. Choose **YouTube** or **Local file**.
3. Scan the source.
4. If a usable subtitle track exists, select it and choose **Extract existing subtitles**.
5. If captions are missing, image-based, or blocked by YouTube, open **Local transcription · Whisper** and choose **Transcribe locally**.
6. DubLocal returns an SRT file and a timed subtitle preview.

See the [User Guide](docs/USER_GUIDE.md) for the same workflow with model choices, rate-limit behaviour and practical examples.

## Updates without Terminal

Open **DubLocal updates** inside the app and use:

- **Check for updates** — contacts the configured GitHub upstream only when you ask;
- **Install update** — accepts only a clean, fast-forward update and refreshes the current Python environment;
- **Restart DubLocal** — restarts through the native launcher so the new code is loaded.

The updater deliberately refuses to overwrite local edits or guess through divergent Git history. Developer checkouts remain safe.

Manual `git pull` remains available as a fallback; see [Installation → Updating](docs/INSTALLATION.md).

## How the local fallback works

```text
YouTube / local media
        ↓
scan source
        ↓
usable captions? ── yes ──→ extract
        │
        no / blocked
        ↓
local whisper.cpp transcription
        ↓
normalized timed SRT
        ↓
next: translation
        ↓
then: Kokoro TTS → timing → audio mix → rendered export
```

For YouTube, local transcription may still need to fetch the video's audio. DubLocal does not bypass DRM, access controls or platform restrictions.

## Privacy and storage

Media processing is local by default. The app binds to `127.0.0.1`, not your LAN.

Whisper model weights are optional and stored outside the Git repository in the normal macOS application-data location. Runtime logs live under:

```text
~/.dublocal/logs/dublocal.log
```

DubLocal contacts GitHub for update checks only when you press **Check for updates** or **Install update**. YouTube is contacted only for YouTube-source operations.

## If something goes wrong

Start with [Troubleshooting](docs/TROUBLESHOOTING.md). It covers the problems most likely to be confusing: YouTube HTTP 429, missing FFmpeg, missing `whisper.cpp`, model problems, a blocked updater, launcher startup failures, and Git working-tree warnings.

## Roadmap

- ✅ local source inspection and subtitle extraction
- ✅ YouTube caption discovery and controlled rate-limit handling
- ✅ normalized subtitle timeline
- ✅ local `whisper.cpp` transcription and model manager
- ✅ native macOS launcher
- ✅ safe in-app GitHub updater
- ☐ translation backend and translation model manager
- ☐ Kokoro TTS backend
- ☐ speech timing and original-audio ducking
- ☐ rendered preview/export
- ☐ signed/notarized macOS release packaging

Contributor-facing design notes are in [Architecture](docs/ARCHITECTURE.md).

## Legal

DubLocal is a media-processing tool. Use it only with media you have the right or legal authority to download, translate, modify or redistribute. The project does not grant rights to third-party content and does not implement DRM or access-control circumvention.

DubLocal itself is licensed under Apache-2.0. Third-party software and model weights keep their own licences; see [Third-party licences](THIRD_PARTY_LICENSES.md) and [Model licence registry](MODEL_LICENSES.json).
