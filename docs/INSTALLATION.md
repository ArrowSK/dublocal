# Installing DubLocal on macOS

DubLocal currently uses a Git checkout as its application source, but after the first setup it behaves like a normal local Mac utility: you launch **DubLocal.app**, update it from inside the app, and manage optional AI models from the relevant panels.

The first installation is the only part that should normally require Terminal.

## What you need

The initial support target is macOS 13 or newer on Apple Silicon or Intel.

DubLocal needs Python 3.11+, FFmpeg/ffprobe for media work, and `whisper.cpp` if you want local transcription. The installer can bootstrap Python and offer FFmpeg/whisper.cpp through Homebrew when Homebrew is already available.

You do **not** need PyTorch, Transformers or translation models just to install and launch DubLocal. M3 translation remains optional and is prepared later from inside the app.

## First installation

Open Terminal and run:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer walks through the required local pieces, creates DubLocal's private Python environment and builds the branded Mac launchers:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

If Python 3.11+ is missing and Homebrew is available, the installer can offer to install it. It also checks FFmpeg and `whisper-cli` and can offer the corresponding Homebrew packages.

The installer does not silently download Whisper or translation model weights.

## After installation

Open `~/Applications/DubLocal.app`. You can drag it to the Dock if you want.

The launcher starts DubLocal only on:

```text
http://127.0.0.1:7861
```

That address is local to your Mac. It is deliberately separate from other local apps and is not a public Gradio share link.

The launcher offers three choices:

- **Launch / Open** — open the existing instance or start DubLocal if it is not running.
- **Stop All & Launch** — stop DubLocal processes and start a clean instance. This is useful after an update.
- **Cancel** — do nothing.

`Stop DubLocal.app` stops DubLocal without requiring Terminal.

## Install a Whisper model only when you need transcription

Inside DubLocal open **Local transcription · Whisper**.

Choose Tiny, Base or Small and click **Install / verify model**. Base (~142 MiB) is the recommended starting point.

Whisper models are stored outside the Git checkout and survive normal application updates.

## Prepare local translation only when you need it

M3 adds a second optional layer. After you have an extracted or transcribed SRT, open **Local translation**, choose the subtitle language and target language, then click **Prepare translation**.

On first use this installs the optional local translation runtime into DubLocal's `.venv`:

```text
PyTorch
Transformers
SentencePiece
safetensors
```

It then downloads only the pinned Apache-2.0 OPUS model route required by your language choice:

```text
many languages → English    ~310 MiB
English → many languages    ~310 MiB
```

English ↔ another language uses one model. Two non-English languages use both models because M3 pivots locally through English.

The weight file is SHA-256 checked before use. Translation models are stored in the normal macOS application-data area, outside `~/dublocal`.

Nothing is sent to a cloud translation API as a fallback.

## Updating after the first installation

Normal updates should now be done inside DubLocal.

Open **DubLocal updates** and use:

**Check for updates → Install update → Restart DubLocal**

The updater performs a Git fetch, checks that your installation is a clean fast-forward, installs the new code, refreshes the core Python package and then lets you restart through the existing launcher.

It will refuse to overwrite local changes or resolve a diverged Git history automatically.

If the in-app updater itself is unavailable because you are on a very old build, the manual recovery path is:

```bash
cd ~/dublocal
git pull
zsh scripts/macos/install-launcher.sh
```

## Where DubLocal keeps things

The repository contains application code:

```text
~/dublocal/
```

Launcher runtime state and logs live under:

```text
~/.dublocal/
```

The main launcher log is:

```text
~/.dublocal/logs/dublocal.log
```

AI models and temporary processing jobs use normal macOS application-data/cache paths selected by `platformdirs`. They are intentionally kept outside the repository so updates do not delete them or make the Git checkout dirty.

## Uninstalling the development build

There is not yet a signed `.dmg` uninstaller. If you decide to remove this development build, stop DubLocal first. The code checkout, launchers, optional models and cache are deliberately separate, so each can be removed independently.

A future signed/notarized packaging milestone will replace this developer-oriented installation with a conventional Mac distribution.

If installation fails, use [TROUBLESHOOTING.md](TROUBLESHOOTING.md) before deleting the environment and starting over.
