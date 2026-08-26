# Installing DubLocal on macOS

**Current development build: v0.4.0.dev0 — M4 Local Voice**

DubLocal currently uses a Git checkout as its application source, but after first setup it behaves like a normal local Mac utility: open **DubLocal.app**, update or repair it from inside the app, and prepare optional AI resources only when needed.

There is not yet a packaged GitHub Release/DMG. `v0.4.0.dev0` is the current M4 development build; see [CHANGELOG.md](../CHANGELOG.md).

## What you need

The initial support target is macOS 13 or newer on Apple Silicon or Intel.

The base application needs Python 3.11+ and uses FFmpeg/ffprobe for local media work. `whisper.cpp` is needed only for local transcription. The installer can bootstrap Python and offer FFmpeg/whisper.cpp through Homebrew when available.

You do **not** need PyTorch, Transformers, Kokoro, OPUS or model weights merely to install and launch DubLocal. Optional AI resources are prepared later from **Settings → Model Manager**.

## First installation

Open Terminal and run:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates the managed DubLocal environment plus:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

If Python 3.11+ is missing and Homebrew is available, the installer can offer to install it. It also checks FFmpeg and `whisper-cli` and can offer their Homebrew packages.

The installer does not silently download Whisper, translation or Kokoro model/voice assets.

## Launching

Open `~/Applications/DubLocal.app` or drag it to the Dock.

DubLocal listens only on:

```text
http://127.0.0.1:7861
```

The launcher offers:

- **Launch / Open** — use the current instance or start one.
- **Stop All & Launch** — stop DubLocal processes and start a clean instance, useful after an update.
- **Cancel** — do nothing.

`Stop DubLocal.app` stops the service without Terminal.

## Main and Settings

Ordinary media work happens on **Main**. Application maintenance lives under **Settings**:

- **Settings → Updates** — update, repair, restart.
- **Settings → Model Manager** — Whisper, OPUS translation and Kokoro resources.
- **Settings → Local Resources** — detected FFmpeg, ffprobe, whisper.cpp, Hugging Face cache and reusable external Python runtimes.

This keeps model installation and maintenance out of the normal processing flow.

## Reuse first, install second

DubLocal tries not to duplicate resources already present on the Mac.

### System executables

FFmpeg, ffprobe and `whisper-cli` are reused in place when found. DubLocal does not make private copies simply because another application installed them first.

### Model caches

OPUS translation and Kokoro use the normal Hugging Face cache (`HF_HUB_CACHE`, `HF_HOME`, `XDG_CACHE_HOME`, or the default cache location). Compatible assets already present there can be reused rather than downloaded into another private cache.

Removing a DubLocal OPUS registration leaves the shared Hugging Face snapshot intact because another local application may still rely on it.

### Python environments

Python virtual environments cannot safely be merged. DubLocal never adds another application's `site-packages` to its own interpreter.

A backend that supports reuse instead starts the compatible environment's own Python as a separate worker process and exchanges narrow structured input/output with DubLocal.

M4 also fixes a macOS-specific discovery issue: a venv's `bin/python` is commonly a symlink to a shared framework Python. DubLocal preserves the venv executable path instead of resolving that symlink, so two separate environments remain distinguishable even if their underlying Python binary is the same.

Inspect the current result under **Settings → Local Resources**.

## Whisper models

Open **Settings → Model Manager → Whisper · transcription**. Select Tiny, Base or Small and click **Install / verify model**. Base (~142 MiB) is the recommended starting point.

Whisper model files are outside the Git checkout and survive app updates/repair.

## Translation resources

Open **Settings → Model Manager → OPUS · subtitle translation**.

Choose the model set you need:

- **English → supported languages** — one ~310 MiB model;
- **Supported languages → English** — the opposite ~310 MiB model;
- **Non-English ↔ non-English** — both models, because translation pivots locally through English.

Then click **Install / verify required model(s)**.

DubLocal first looks for a compatible existing translation runtime. Only if none is available does it install its optional translation stack. Exact OPUS safetensors weights are pinned and SHA-256 verified before use.

There is no cloud translation fallback.

## Kokoro resources

Open **Settings → Model Manager → Kokoro · voice generation**.

Choose a supported language/voice and click **Prepare / verify Kokoro**.

DubLocal first searches for a compatible existing Kokoro environment. If one is found, DubLocal runs Kokoro through that environment's own Python worker rather than duplicating its packages. If none exists, DubLocal can install the optional Kokoro runtime into its own `.venv`.

Preparation also verifies that the selected Kokoro frontend/voice can load. Missing official model or voice assets may be downloaded into the shared Hugging Face cache at this point.

Official Kokoro language support exposed by M4 is American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese. Translation targets such as Hungarian, Russian and German remain subtitle-only with the current TTS backend.

## Updating inside DubLocal

Open **Settings → Updates**.

For the normal case:

**Check for updates → Install update → Restart DubLocal**

The updater compares:

- the currently running DubLocal version;
- the local Git checkout;
- official `ArrowSK/dublocal` → `main`.

It accepts only a clean fast-forward. Normal updates never overwrite tracked local edits and never rewrite local commits or diverged history.

## Repair installation

The same **Settings → Updates** panel includes **Repair installation**.

Two cases are handled:

1. **The Git checkout is correct but the managed Python core is stale.** Repair refreshes the core and verifies the imported version/path.
2. **Tracked DubLocal program files were modified locally.** If you explicitly tick the repair confirmation, DubLocal saves the tracked diff as a patch, restores official tracked files from GitHub `main`, refreshes/verifies the core and restarts.

Patch backups are kept under:

```text
~/.dublocal/repair-backups/
```

Repair intentionally preserves optional models, shared caches, generated jobs and untracked user files. It refuses to rewrite local commits or diverged Git history.

## Manual recovery

If you are on an older build that does not have the current updater/repair UI:

```bash
cd ~/dublocal
git pull
zsh scripts/macos/install-launcher.sh
```

After the current updater is installed, ordinary maintenance should be done from inside DubLocal.

## Where DubLocal keeps things

```text
~/dublocal/                         application Git checkout
~/.dublocal/logs/                   launcher logs
~/.dublocal/repair-backups/         repair patch backups
~/Library/.../DubLocal/models/      app-specific model registrations / legacy copies
~/.cache/huggingface/hub/           default shared Hugging Face cache
~/Library/Caches/.../DubLocal/jobs/ generated SRT/WAV/manifest/intermediate files
```

The exact application-data/cache directories are resolved with `platformdirs`, and Hugging Face cache environment variables are respected.

## Removing the development build

There is not yet a signed `.dmg` uninstaller. Code, launchers, optional models and caches are deliberately separated so they can eventually be managed independently.

If something fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) before deleting the entire environment.
