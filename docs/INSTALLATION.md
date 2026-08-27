# Installing DubLocal on macOS

**Current development build: v0.5.1.dev0 — Voice Match + Export Refinement**

DubLocal currently uses a Git checkout as its application source, but after first setup it behaves like a normal local Mac utility: launch **DubLocal.app**, update/repair inside the app, and install optional models only when you need them.

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

It can bootstrap Python 3.11+ and offer FFmpeg/whisper.cpp through Homebrew when required. It does not silently download optional AI model weights.

After installation, ordinary use is through **DubLocal.app**.

## What DubLocal reuses

DubLocal follows a reuse-first policy:

- existing FFmpeg/ffprobe executables;
- existing `whisper-cli`;
- existing compatible llama.cpp executables;
- shared Hugging Face model cache;
- compatible external Python runtimes such as Kokoro, through isolated worker processes.

Python virtual environments are never merged and another application's `site-packages` is never injected into DubLocal.

Open **Settings → Local Resources** to see what is being reused.

## Models installed only on request

### Whisper

Open **Settings → Model Manager → Whisper**.

Tiny, Base, Small and optional Accurate Large-v3-Turbo-Q5 are available. Base remains the normal starting point; Accurate is intended for songs, accents and difficult/noisy speech.

### Contextual translation

Open **Settings → Model Manager → Contextual translation** and click **Prepare / verify contextual translation**.

DubLocal detects the Mac hardware and prepares only its recommended profile:

```text
Apple Silicon < 12 GB     Qwen3 4B · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review on · up to 24k input
Intel < 24 GB             Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context
```

The actual llama.cpp runtime context allocation scales with this profile too. This matters particularly on low-memory Apple Silicon.

Approximate contextual model sizes:

- Qwen3 4B Q4_K_M — 2.5 GB.
- Qwen3 8B Q4_K_M — 5.03 GB.

Both are downloaded only when needed, pinned/checksum-verified and stored through the shared Hugging Face cache. There is no cloud translation fallback.

### Fast legacy translation

OPUS remains an explicit smaller/faster sentence-level option under **Fast legacy translation · OPUS**.

### Kokoro

Open **Settings → Model Manager → Kokoro**. DubLocal reuses a compatible external Kokoro environment first. Only if no reusable environment exists does it prepare another local runtime.

The v0.5.1 automatic voice matcher does not install or load a second TTS model. It performs a lightweight local acoustic analysis and can switch Kokoro voice presets per subtitle segment while the same Kokoro language pipeline remains loaded.

## Export has no new heavy AI model dependency

The v0.5/v0.5.1 export path uses FFmpeg/ffprobe plus the existing voice output. Automatic original-vocal-range matching also uses FFmpeg + NumPy only; no diarization or source-separation model is downloaded.

Export can:

- timing-fit generated voice segments;
- strongly suppress the original soundtrack across timed dialogue/singing windows;
- replace the primary audio or append a second dubbed track;
- embed generated original and translated subtitles as selectable streams;
- stream-copy the video where compatible;
- choose a lower YouTube source resolution before download without local video encoding;
- optionally downscale a local video only when the user explicitly selects a lower output resolution.

For local downscaling DubLocal uses FFmpeg's Apple VideoToolbox H.264 encoder. **Original / best available** remains the no-video-recode default.

MKV is the recommended container. MP4 is used only when the selected streams can be packaged compatibly; DubLocal does not silently start a video transcode merely to satisfy MP4.

## Updating

Open **Settings → Updates** and use:

**Check for updates → Install update → Restart DubLocal**

Normal updates accept only a clean fast-forward from official `ArrowSK/dublocal` `main`. They do not overwrite tracked local edits or rewrite divergent Git history.

## Repair installation

Use **Repair installation** when the checkout or managed Python environment is inconsistent.

If tracked files were modified, DubLocal can save the diff as a patch under:

```text
~/.dublocal/repair-backups/
```

then restore official source and refresh the Python core. Models, shared caches, generated jobs and untracked files are preserved.

## Launcher details

DubLocal listens only on the local machine at:

```text
http://127.0.0.1:7861
```

`Stop DubLocal.app` stops the service. After an update the launcher can perform **Stop All & Launch**.

Contextual translation may also create a temporary loopback-only llama-server on `127.0.0.1` with an ephemeral port for the duration of a translation job.

## Where files live

```text
~/dublocal/                         application Git checkout
~/.dublocal/logs/                   launcher logs
~/.dublocal/repair-backups/         repair patch backups
~/Library/.../DubLocal/models/      app-specific model registrations
~/.cache/huggingface/hub/           default shared Hugging Face cache
~/Library/Caches/.../DubLocal/jobs/ generated/intermediate job files
```

The jobs cache includes temporary source media, voice-analysis PCM, timing-fitted voice segments, dubbed audio mixes, generated subtitle tracks and remuxed outputs in addition to transcription/translation/TTS intermediates.

Normal startup removes job folders older than 24 hours and caps this temporary cache at 4 GiB. Persistent models/shared Hugging Face assets are outside that lifecycle.

Exact paths use `platformdirs`; Hugging Face cache environment variables are respected.

## Older-build recovery

If the installed build is too old to use the current updater:

```bash
cd ~/dublocal
git pull
zsh scripts/macos/install-launcher.sh
```

Once the current updater is present, normal maintenance should happen inside DubLocal.

If something fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) before deleting models or rebuilding everything.