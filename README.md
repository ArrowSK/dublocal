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

M3 adds local subtitle translation on top of the timestamped M2 timeline and improves real-world local installation management:

- local OPUS subtitle translation with exact timing preservation;
- shared Hugging Face model-cache reuse instead of unnecessary duplicate model copies;
- safe discovery/reuse of compatible external Python runtimes;
- in-app **Repair installation** for modified/stale Git-based installs;
- dedicated **Main** and **Settings** areas;
- **Settings → Updates**, **Model Manager**, and **Local Resources** subtabs.

There is currently **no packaged GitHub Release**. `v0.3.0.dev0` is the latest development build on `main`. See [CHANGELOG.md](CHANGELOG.md) for the build history.

## What works today

| Stage | Status | What DubLocal does |
| --- | --- | --- |
| Media input | ✅ | YouTube URL or local video/audio |
| Existing subtitles | ✅ | Finds embedded/local and YouTube caption tracks |
| Missing captions | ✅ | Creates timestamped subtitles locally with whisper.cpp |
| Subtitle translation | ✅ M3 | Translates the timed SRT locally with optional OPUS models |
| AI voice | Next | Kokoro local TTS backend |
| Dubbing mix | Planned | Timing fit, original-audio ducking and speech overlay |
| Media export | Planned | Stream-copy compatible video; replace/add dubbed audio track |

## Main vs Settings

DubLocal keeps ordinary processing separate from maintenance.

### Main

Use **Main** for the current job:

1. Choose **YouTube** or **Local file** and scan it.
2. Extract an existing subtitle track or run **Transcribe locally**.
3. Choose the subtitle language and target language.
4. Click **Translate subtitles**.

### Settings

Use **Settings** for the application itself:

- **Updates** — check/install updates, repair installation, restart.
- **Model Manager** — install/verify/remove Whisper and OPUS translation models; Kokoro joins here in M4.
- **Local Resources** — inspect FFmpeg, ffprobe, whisper.cpp, Hugging Face cache and reusable external Python runtimes.

So, to install a translation model now:

**Settings → Model Manager → OPUS · subtitle translation → choose model set → Install / verify required model(s)**

English → another supported language needs one ~310 MiB model. Another supported language → English needs the opposite ~310 MiB model. Non-English ↔ non-English uses both through an English pivot.

## Reuse first, install second

DubLocal deliberately avoids duplicating large local dependencies when safe reuse is possible.

System tools such as **FFmpeg**, **ffprobe** and **whisper.cpp** are used where they are already installed. Translation models use the standard shared Hugging Face cache. If the exact pinned OPUS snapshot already exists because another compatible local app downloaded it, DubLocal registers that same snapshot instead of storing a second copy.

Python virtual environments are isolation boundaries. DubLocal never imports another application's `site-packages` directly. Compatible external runtimes can instead be used through isolated worker processes. This mechanism already supports M3 translation and is the basis for reusing an existing Kokoro installation in M4.

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

After that, normal use is through **DubLocal.app**, not Terminal.

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for the detailed installation guide.

## Updates and repair

Open **Settings → Updates**.

Normal flow:

**Check for updates → Install update → Restart DubLocal**

Normal updates accept only a clean fast-forward from official `ArrowSK/dublocal` `main` and never overwrite tracked local edits.

**Repair installation** is the explicit recovery path. It can save modified tracked program files as a patch backup, restore official files, refresh/verify the managed Python core and restart cleanly without deleting models, caches, generated jobs or untracked user files.

## Supported M3 translation languages

The current UI allowlist is:

English, Hungarian, Russian, German, French, Spanish, Italian, Portuguese, Polish, Ukrainian, Serbian and Croatian.

The underlying OPUS models cover more languages, but DubLocal intentionally exposes a smaller tested set first.

## Planned dubbed-media output

DubLocal will not re-encode video merely because a dubbed audio stream is being created. Where the source codec/container is compatible, FFmpeg will stream-copy the original video and process only the new audio.

The planned output choice is:

- **Replace primary audio — default:** make the DubLocal mixed soundtrack the default/primary audio stream while keeping music/effects underneath the translated speech.
- **Add dubbed audio as second track:** preserve the original audio unchanged and add the DubLocal mix as another selectable audio stream.

MKV will be preferred for maximum multi-track preservation; MP4 remains available when the selected streams/codecs are compatible.

## Where files live

```text
~/dublocal/                         cloned application source
~/Library/.../DubLocal/models/      DubLocal model registrations / legacy local models
~/.cache/huggingface/hub/           normal shared Hugging Face model cache (default)
~/Library/Caches/.../DubLocal/jobs/ generated/intermediate job files
~/.dublocal/logs/                   launcher log
~/.dublocal/repair-backups/         patch backups created by Repair installation
```

Exact platform data/cache locations are resolved using `platformdirs`; `HF_HOME` and `HF_HUB_CACHE` are respected.

## Documentation

- [Changelog](CHANGELOG.md) — current development build and milestone history.
- [User guide](docs/USER_GUIDE.md) — Main, Settings, Model Manager and normal day-to-day workflow.
- [Installation](docs/INSTALLATION.md) — launcher, first install, updates and repair.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — practical recovery steps.
- [Architecture](docs/ARCHITECTURE.md) — local pipeline and reusable-backend design.
- [Third-party licences](THIRD_PARTY_LICENSES.md) and [model registry](MODEL_LICENSES.json).

## Roadmap

```text
M1  Source + existing captions                         ✅
M2  Local transcription / Whisper                      ✅ validated
M3  Local subtitle translation + Settings/Model Manager ✅ current
M4  Kokoro local voice generation                      next
M5  Voice timing + audio mix + stream-copy export      planned
M6  Preview + final rendered/remuxed media              planned
M7  Signed/notarized Mac packaging                     planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json` for the current inventory.
