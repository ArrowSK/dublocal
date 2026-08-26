<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, translation and voice-over tooling for macOS.<br>
  Your media stays on your Mac unless you explicitly use a remote media source such as YouTube.
</p>

<p align="center">
  <strong>M3 development build</strong> · macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal is for a simple problem: you have a video or audio file — or a YouTube link you are allowed to process — and you want timed subtitles in another language without sending the media through a cloud transcription or translation service.

The long-term goal is local AI voice-over dubbing. The current build already handles the first three stages reliably: subtitle acquisition, local speech transcription and local subtitle translation.

## What works today

| Stage | Status | What DubLocal does |
| --- | --- | --- |
| Media input | ✅ | YouTube URL or local video/audio |
| Existing subtitles | ✅ | Finds embedded/local and YouTube caption tracks |
| Missing captions | ✅ | Creates timestamped subtitles locally with whisper.cpp |
| Subtitle translation | ✅ M3 | Translates the timed SRT locally with optional OPUS models |
| AI voice | Next | Kokoro local TTS backend |
| Dubbing mix | Planned | Timing fit, original-audio ducking and speech overlay |
| Video render | Planned | Preview and final media export |

## The normal workflow

1. Open **DubLocal.app**.
2. Choose **YouTube** or **Local file**, then scan the source.
3. If good subtitles already exist, extract them. If not, use **Transcribe locally**.
4. In **Local translation**, choose the subtitle language and the language you want.
5. The first time you use a translation route, click **Prepare translation**. DubLocal installs only the optional runtime and model(s) that route needs.
6. Click **Translate subtitles** and download the translated SRT.

The timestamps are kept unchanged during translation, so the translated subtitle file remains synchronized with the original media.

## Local-first means optional models stay optional

DubLocal deliberately keeps the base installation small. AI weights are not silently downloaded.

For transcription, you choose a Whisper model yourself. **Base** (~142 MiB) is the recommended starting point.

For translation, DubLocal uses two allowlisted Apache-2.0 Helsinki-NLP OPUS models:

- many supported languages → English, ~310 MiB;
- English → many supported languages, ~310 MiB.

An English ↔ another-language translation needs one model. A translation between two non-English languages uses English as a local pivot and therefore needs both. Exact pinned revisions and checksums are recorded in `MODEL_LICENSES.json`.

There is no silent cloud transcription or translation fallback.

## Install on macOS

The initial development installation uses Git so DubLocal can update itself safely from this repository.

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

It also creates DubLocal's private Python environment, checks FFmpeg, can install the small `whisper.cpp` engine through Homebrew, and generates the branded macOS icon.

After that, normal use is through **DubLocal.app** — not Terminal.

For a calmer step-by-step install guide, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Updating without Terminal

Open **DubLocal updates** inside the app:

**Check for updates → Install update → Restart DubLocal**

The updater only accepts a clean fast-forward from the configured GitHub branch. If the installation folder contains local edits or divergent commits, DubLocal stops and explains why instead of overwriting anything.

## Supported M3 translation languages

The current UI allowlist is:

English, Hungarian, Russian, German, French, Spanish, Italian, Portuguese, Polish, Ukrainian, Serbian and Croatian.

The underlying OPUS models cover more languages, but DubLocal intentionally exposes a smaller tested set first. More languages can be added after their model behavior and identifiers are validated.

## Where files live

DubLocal separates code, models and temporary jobs:

```text
~/dublocal/                         cloned application source
~/Library/.../DubLocal/models/      optional local AI models
~/Library/Caches/.../DubLocal/jobs/ generated/intermediate job files
~/.dublocal/logs/                   launcher log
```

The exact `~/Library` paths are chosen using the normal macOS application-data conventions through `platformdirs`.

Removing a translation or Whisper model does not uninstall DubLocal.

## Documentation

- [User guide](docs/USER_GUIDE.md) — how to use DubLocal without needing to understand the implementation.
- [Installation](docs/INSTALLATION.md) — first installation, launcher and updates.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — practical fixes for the errors users are likely to encounter.
- [Architecture](docs/ARCHITECTURE.md) — how the local pipeline is separated into replaceable backends.
- [Third-party licences](THIRD_PARTY_LICENSES.md) and [model registry](MODEL_LICENSES.json) — what DubLocal depends on and why.

## Roadmap

```text
M1  Source + existing captions              ✅
M2  Local transcription / Whisper           ✅
M3  Local subtitle translation              ✅ implementation; validation in progress
M4  Kokoro local voice generation            next
M5  Voice timing + original-audio ducking    planned
M6  Preview + rendered media export          planned
M7  Signed/notarized Mac packaging           planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json` for the current inventory.
