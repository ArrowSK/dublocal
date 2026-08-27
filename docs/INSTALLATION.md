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

### Contextual translation — Recommended for this Mac

Open **Settings → Model Manager → Contextual translation** and click **Prepare / verify contextual translation**.

DubLocal first detects the Mac architecture and physical memory, then prepares only the contextual model recommended for that hardware. The ordinary Main workflow therefore stays simple; it shows **Recommended for this Mac · Lightweight / Balanced / Best quality** rather than asking the user to choose from a model matrix.

Current conservative defaults are:

```text
Apple Silicon < 12 GB     Qwen3 4B · review off · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · review off · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · 24k input cap
Intel < 24 GB             Qwen3 4B · review off · smaller context
Intel 24 GB+              Qwen3 8B · review off · reduced context
```

That preparation action:

1. detects the recommended translation profile for the current Mac;
2. reuses an existing compatible `llama.cpp` command when available;
3. otherwise installs `llama.cpp` through Homebrew;
4. downloads only the recommended official Qwen GGUF into the shared Hugging Face cache;
5. verifies the pinned checksum before registering the model with DubLocal.

Approximate contextual model sizes:

- **Qwen3 4B Q4_K_M** — 2.5 GB; lightweight profile;
- **Qwen3 8B Q4_K_M** — 5.03 GB; balanced/best profiles.

Both are local Apache-2.0 model releases. There is no cloud translation fallback.

The hardware profile also controls the **actual llama.cpp context allocation**, not only the amount of prompt text. For example, an 8 GB M1 does not reserve the model's full 32k context while receiving only an 8k prompt; DubLocal starts llama.cpp with a smaller runtime context to reduce unified-memory and swap pressure.

If another contextual Qwen model was already registered by an earlier DubLocal build, Model Manager reports it as the alternate model. Preparing contextual translation does not download both models merely because both are supported.

Removing DubLocal contextual models removes DubLocal's registrations/links. It does not erase the shared Hugging Face cache or uninstall `llama.cpp`, because another local application may use them.

### Fast legacy translation — optional

The OPUS models remain under Settings → Model Manager → **Fast legacy translation · OPUS**. They are smaller (~310 MiB per direction) but translate sentence-by-sentence and are not the recommended contextual path.

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

The contextual runtime also uses a temporary loopback-only llama-server on `127.0.0.1` when that executable is available. Its port is selected dynamically for the translation job and is not exposed on the LAN.

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
