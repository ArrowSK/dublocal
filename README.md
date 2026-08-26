<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, translation and voice-over tooling for macOS.<br>
  Your media stays on your Mac unless you explicitly use a remote source such as YouTube.
</p>

<p align="center">
  <strong>Current development build: v0.3.0.dev0 · M3 Local Translation</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal is for a simple problem: you have a video or audio file — or a YouTube link you are allowed to process — and you want timed subtitles in another language without sending the media through a cloud transcription or translation service.

The long-term goal is local AI voice-over dubbing. The current build already covers source/caption acquisition, local Whisper transcription and local subtitle translation.

## Latest development build — v0.3.0.dev0 / M3

M3 adds local subtitle translation on top of the timestamped M2 timeline. It also improves the application infrastructure around real-world local installs:

- local OPUS subtitle translation with exact timing preservation;
- shared Hugging Face model-cache reuse instead of unnecessary duplicate model copies;
- discovery of compatible local Python runtimes, including an existing Kokoro environment, for safe separate-process reuse by supported backends;
- an in-app **Repair installation** path for modified/stale Git-based installs, modeled on NarRoam Studio's recovery behavior;
- version-aware updater output showing the running build, local checkout and GitHub `main`.

There is currently **no packaged GitHub Release**. `v0.3.0.dev0` is the latest development build on `main`; packaged releases will begin once the corresponding build and macOS distribution are ready. See [CHANGELOG.md](CHANGELOG.md) for the release/build history.

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
5. The first time a translation route is used, click **Prepare translation**. DubLocal first checks what compatible local resources already exist, then obtains only what is still required.
6. Click **Translate subtitles** and save the translated SRT.

The timestamps are kept unchanged during translation, so the translated subtitle file stays synchronized with the source media.

## Reuse first, install second

DubLocal deliberately avoids duplicating large local dependencies when safe reuse is possible.

System tools such as **FFmpeg**, **ffprobe** and **whisper.cpp** are used where they are already installed. Translation models use the standard shared Hugging Face cache. If the exact pinned OPUS snapshot already exists because another local app downloaded it, DubLocal registers that same local snapshot instead of storing a second model copy.

Python virtual environments need more care. Importing another application's `site-packages` directly into DubLocal would make both applications fragile. Instead, DubLocal can discover compatible external Python environments and supported backends can run them as isolated worker processes. The M3 translation backend can already reuse a compatible external PyTorch/Transformers runtime this way. The same mechanism is intended for M4 Kokoro, so an existing compatible Kokoro installation can be reused rather than installed again.

Open **Reusable local resources** inside DubLocal to see what has been detected.

## Local-first means optional models stay optional

AI weights are never silently downloaded.

For transcription, choose a Whisper model yourself. **Base** (~142 MiB) is the recommended starting point.

For translation, DubLocal uses two allowlisted Apache-2.0 Helsinki-NLP OPUS models:

- many supported languages → English, ~310 MiB;
- English → many supported languages, ~310 MiB.

English ↔ another language needs one model. Translation between two non-English languages uses English as a local pivot and needs both. Exact pinned revisions and checksums are recorded in `MODEL_LICENSES.json`.

There is no silent cloud transcription or translation fallback.

## Install on macOS

The current development installation uses Git so DubLocal can update and repair itself from the official repository.

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

It also creates DubLocal's managed Python environment, checks FFmpeg, can install the small `whisper.cpp` engine through Homebrew, and generates the branded macOS icon.

After that, normal use is through **DubLocal.app** — not Terminal.

For a step-by-step install guide, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Updating and repairing without Terminal

Open **DubLocal updates & repair** inside the app.

For a normal update:

**Check for updates → Install update → Restart DubLocal**

Normal updates accept only a clean fast-forward from official `ArrowSK/dublocal` `main`. They never overwrite tracked local edits.

If the checkout is current but the running Python core is stale, DubLocal can repair the managed environment. If tracked DubLocal program files were modified, **Repair installation** can optionally save those changes as a patch under `~/.dublocal/repair-backups/`, restore official tracked files, refresh and verify the managed core, then restart cleanly. It does not delete models, shared caches, generated jobs or untracked user files. Local commits and diverged Git history are still left for manual review.

## Supported M3 translation languages

The current UI allowlist is:

English, Hungarian, Russian, German, French, Spanish, Italian, Portuguese, Polish, Ukrainian, Serbian and Croatian.

The underlying OPUS models cover more languages, but DubLocal intentionally exposes a smaller tested set first.

## Where files live

DubLocal separates application code from data and reusable caches:

```text
~/dublocal/                         cloned application source
~/Library/.../DubLocal/models/      DubLocal model registrations / legacy local models
~/.cache/huggingface/hub/           normal shared Hugging Face model cache (default)
~/Library/Caches/.../DubLocal/jobs/ generated/intermediate job files
~/.dublocal/logs/                   launcher log
~/.dublocal/repair-backups/         patch backups created by Repair installation
```

The exact platform data/cache locations are resolved using `platformdirs` and environment variables such as `HF_HOME` / `HF_HUB_CACHE` are respected.

Removing a shared translation model registration from DubLocal does not delete the underlying shared Hugging Face cache, because another local application may still rely on it.

## Documentation

- [Changelog](CHANGELOG.md) — current development build and what changed in each milestone.
- [User guide](docs/USER_GUIDE.md) — day-to-day use without needing to understand the implementation.
- [Installation](docs/INSTALLATION.md) — first installation, launcher, updates and repair.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — practical fixes for likely failures.
- [Architecture](docs/ARCHITECTURE.md) — how the local pipeline is separated into replaceable backends.
- [Third-party licences](THIRD_PARTY_LICENSES.md) and [model registry](MODEL_LICENSES.json) — current dependency/model inventory.

## Roadmap

```text
M1  Source + existing captions               ✅
M2  Local transcription / Whisper            ✅ validated
M3  Local subtitle translation               ✅ implementation; validation in progress
M4  Kokoro local voice generation            next
M5  Voice timing + original-audio ducking    planned
M6  Preview + rendered media export          planned
M7  Signed/notarized Mac packaging           planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json` for the current inventory.
