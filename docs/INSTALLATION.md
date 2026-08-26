# Installing DubLocal on macOS

**Current development build: v0.3.0.dev0 — M3 Local Translation**

DubLocal currently uses a Git checkout as its application source, but after first setup it behaves like a normal local Mac utility: open **DubLocal.app**, update or repair it from inside the app, and install optional AI resources only when needed.

There is not yet a packaged GitHub Release/DMG. `v0.3.0.dev0` is the current development build on `main`; see [CHANGELOG.md](../CHANGELOG.md).

## What you need

The initial support target is macOS 13 or newer on Apple Silicon or Intel.

The base application needs Python 3.11+ and uses FFmpeg/ffprobe for local media work. `whisper.cpp` is needed only for local transcription. The installer can bootstrap Python and offer FFmpeg/whisper.cpp through Homebrew when available.

You do **not** need PyTorch, Transformers, Kokoro or translation model weights merely to install and launch DubLocal.

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

The installer does not silently download Whisper, translation or voice model weights.

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

## Reuse first, install second

DubLocal tries not to duplicate resources already present on the Mac.

### System executables

FFmpeg, ffprobe and `whisper-cli` are reused in place when found. DubLocal does not make private copies simply because another application installed them first.

### Model caches

M3 translation uses the standard Hugging Face cache (`HF_HUB_CACHE`, `HF_HOME`, `XDG_CACHE_HOME`, or the normal default). If the exact pinned OPUS snapshot already exists locally, Hugging Face reuses it. DubLocal registers a link to that verified snapshot instead of storing another full copy.

Removing the model from DubLocal removes its registration/link but leaves the shared cache intact, because another app may be using it.

### Python environments

Python virtual environments cannot safely be merged. Importing another application's `site-packages` directly into DubLocal can create incompatible versions and make both applications unreliable.

Instead, DubLocal can detect known compatible external Python runtimes. A backend that supports sharing runs that environment in a separate process and exchanges only structured input/output with DubLocal.

M3 translation can reuse a compatible external PyTorch/Transformers stack this way. The same mechanism is intended for M4 Kokoro, so a compatible existing Kokoro environment can be used rather than installed again.

You can inspect detection results in **Reusable local resources** inside the app.

## Whisper models

Open **Local transcription · Whisper**, select Tiny/Base/Small and click **Install / verify model** when required. Base (~142 MiB) is the recommended starting point.

Whisper model files are outside the Git checkout and survive app updates/repair.

## Translation resources

After obtaining an SRT, open **Local translation**, select source/target language and click **Prepare translation**.

DubLocal first looks for a compatible existing translation runtime. Only if none is available does it install the optional translation stack into its own `.venv`:

```text
PyTorch
Transformers
SentencePiece
safetensors
```

It then ensures the required pinned OPUS model snapshot exists in the shared Hugging Face cache. English ↔ another supported language needs one ~310 MiB model; non-English ↔ non-English requires both because M3 pivots locally through English.

The safetensors weight file is SHA-256 verified before the model is registered for use.

There is no cloud translation fallback.

## Updating inside DubLocal

Open **DubLocal updates & repair**.

For the normal case:

**Check for updates → Install update → Restart DubLocal**

The updater compares:

- the currently running DubLocal version;
- the local Git checkout;
- official `ArrowSK/dublocal` → `main`.

It accepts only a clean fast-forward. Normal updates never overwrite tracked local edits and never rewrite local commits or diverged history.

## Repair installation

The same panel includes **Repair installation**, modeled on the NarRoam Studio repair path.

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
~/Library/Caches/.../DubLocal/jobs/ generated/intermediate files
```

The exact application-data/cache directories are resolved with `platformdirs`, and Hugging Face cache environment variables are respected.

## Removing the development build

There is not yet a signed `.dmg` uninstaller. Code, launchers, optional models and caches are deliberately separated so they can eventually be managed independently.

If something fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) before deleting the entire environment.
