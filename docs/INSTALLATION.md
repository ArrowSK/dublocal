# Installing DubLocal on macOS

**Current development build: v0.4.2.dev0 — Subtitle Export + Translation Quality Pass**

DubLocal still uses a Git checkout as its application source, but after first setup it behaves like a normal local Mac utility: open **DubLocal.app**, update/repair inside the app, and install optional models only when you need them.

There is no packaged DMG/GitHub Release yet.

## First installation

DubLocal currently targets macOS 13+ on Apple Silicon and Intel.

Open Terminal once:

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

It can bootstrap Python 3.11+ and offer FFmpeg/whisper.cpp through Homebrew when required. It does **not** silently download AI model weights.

After installation, ordinary use is through **DubLocal.app**.

## What is installed only when requested

### Whisper

Settings → Model Manager → Whisper.

Available local models include Tiny, Base, Small and the optional Accurate Large-v3-Turbo-Q5 model. Base (~142 MiB) remains the normal starting point; Accurate (~547 MiB) is intended for difficult audio such as songs, accents or noisy speech.

### Contextual translation — recommended quality path

Settings → Model Manager → **Contextual translation · Qwen3 8B · quality** → **Prepare / verify contextual translation**.

That action:

1. reuses an existing compatible `llama.cpp` command when available;
2. otherwise installs `llama.cpp` through Homebrew;
3. downloads the official Qwen3 8B Q4_K_M GGUF (~5.03 GB) into the shared Hugging Face cache;
4. verifies the pinned SHA-256 before registering the model with DubLocal.

The model is local and Apache-2.0. Translation has no cloud fallback.

The previous Qwen3 4B development model is no longer selected by v0.4.2. If it was downloaded previously, its shared-cache snapshot may remain because DubLocal does not delete shared model assets that another application could be using.

### Fast legacy translation — optional

The OPUS models remain under Settings → Model Manager → **Fast legacy translation · OPUS**. They are smaller (~310 MiB per direction) but translate sentence-by-sentence and are not the recommended quality path.

### Kokoro

Settings → Model Manager → Kokoro. DubLocal first searches for a compatible existing Kokoro environment and runs it through an isolated Python worker. Only when no reusable environment exists does DubLocal prepare another Kokoro runtime.

## Reuse first, install second

DubLocal deliberately avoids duplicate heavyweight resources when safe reuse is possible.

- FFmpeg, ffprobe, whisper.cpp and llama.cpp executables are reused in place.
- Qwen, OPUS and Kokoro model assets use the normal shared Hugging Face cache.
- Python virtual environments are never merged. Compatible external environments are invoked as isolated workers instead of adding their `site-packages` to DubLocal.

Open **Settings → Local Resources** to see what is being reused.

## Updating

Open **Settings → Updates** and use:

**Check for updates → Install update → Restart DubLocal**

Normal updates accept only a clean fast-forward from official `ArrowSK/dublocal` `main`. They do not overwrite tracked local edits or rewrite divergent Git history.

## Repair installation

Use **Repair installation** when the checkout or managed Python environment is inconsistent.

If tracked program files were modified, DubLocal can save the diff as a patch under:

```text
~/.dublocal/repair-backups/
```

and restore official files before refreshing the Python core. Models, shared caches, generated jobs and untracked user files are preserved.

## Launcher details

DubLocal listens only on the local machine at:

```text
http://127.0.0.1:7861
```

The launcher can open the running instance or perform **Stop All & Launch** after an update. `Stop DubLocal.app` stops the local service without Terminal.

The contextual quality runtime also uses a temporary loopback-only llama-server on `127.0.0.1` when that executable is available. Its port is selected dynamically for the translation job and is not exposed on the LAN.

## Where files live

```text
~/dublocal/                         application Git checkout
~/.dublocal/logs/                   launcher logs
~/.dublocal/repair-backups/         repair patch backups
~/Library/.../DubLocal/models/      app-specific model registrations
~/.cache/huggingface/hub/           default shared Hugging Face cache
~/Library/Caches/.../DubLocal/jobs/ generated/intermediate job files
```

The jobs cache contains temporary audio, subtitles, voice intermediates and contextual-runtime logs. Normal startup removes jobs older than 24 hours and caps this temporary cache at 4 GiB.

Persistent model assets and the shared Hugging Face cache are not automatically pruned as temporary jobs.

Exact data/cache paths use `platformdirs`; Hugging Face cache environment variables are respected.

## Older-build recovery

If you are still on a build too old to use the current updater:

```bash
cd ~/dublocal
git pull
zsh scripts/macos/install-launcher.sh
```

Once the current updater is installed, normal maintenance should happen inside DubLocal.

If something fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) before deleting models or rebuilding the whole environment.
