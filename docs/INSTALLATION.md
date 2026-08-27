# Installing DubLocal on macOS

**Current development build: v0.5.3.dev0 — M5 Stabilization**

DubLocal currently runs from a Git checkout, but after the first setup ordinary use is through the native **DubLocal.app** launcher. Updates, repair and optional models are managed inside the app.

There is no packaged DMG/GitHub Release yet.

## Requirements

- macOS 13+
- Apple Silicon or Intel
- Python 3.11+ (the installer can bootstrap it)
- FFmpeg/ffprobe
- optional whisper.cpp, llama.cpp and AI model weights depending on the features you use

## First installation

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

It can offer Homebrew installation for required native tools. Heavy optional AI models are not silently bundled or downloaded.

## Reuse-first policy

Open **Settings → Local Resources** to see what DubLocal is reusing. The application prefers:

- existing FFmpeg/ffprobe;
- existing `whisper-cli`;
- compatible llama.cpp executables;
- the shared Hugging Face cache;
- compatible external Kokoro Python runtimes through an isolated worker process.

DubLocal never merges virtual environments or injects another application's `site-packages` into its own interpreter.

## Model Manager

### Whisper

Base is the normal starting model. **Accurate · Large v3 Turbo Q5 · 547 MiB** is the stronger option for songs, accents and difficult/noisy audio.

The tiny whisper.cpp Silero VAD asset may be prepared on demand for supported speech-oriented paths. v0.5.3 does not rely on VAD alone: the Accurate music profile has separate no-context/repetition protection and targeted two-pass recovery for suspicious sparse/gap regions.

### Contextual translation

**Settings → Model Manager → Contextual translation → Prepare / verify** installs only the hardware-appropriate Qwen model/profile:

```text
Apple Silicon <12 GB      Qwen3 4B · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review · up to 24k
Intel <24 GB              Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context
```

The runtime KV/context allocation scales too; this is important for 8 GB M1 systems.

### Kokoro

DubLocal first reuses a compatible isolated Kokoro runtime if one is already available. Automatic lower/higher vocal-range matching changes voice presets per segment without loading a second TTS model.

## v0.5.3 has no new heavy model dependency

The new stabilization work is intentionally M1-friendly:

- stable soundtrack loudness and timing fit use FFmpeg DSP;
- subtitle-only packaging is remuxing;
- smarter missing-word recovery reuses the selected Whisper model only for short suspicious ranges;
- on Apple Silicon below 12 GiB, extra ASR recovery is capped at 3 regions / 24 seconds per job.

There is no hidden second full-media transcription pass.

## Export and recoding policy

**Original / best available** remains the default.

For local files, Original uses video stream-copy. Selecting a lower resolution explicitly opts into Apple VideoToolbox H.264 encoding. Audio/subtitle changes alone never imply a video transcode.

For YouTube, a selected maximum resolution constrains source acquisition before final stream-copy.

Export modes include:

- Replace primary audio;
- Add dubbed audio as another track;
- **Package original + subtitles · no dub**.

MKV is recommended for multi-track output. MP4 is available for compatible combinations.

## Updating

Use:

**Settings → Updates → Check for updates → Install update → Restart DubLocal**

Normal updates accept only a clean fast-forward from official `ArrowSK/dublocal` `main` and do not overwrite tracked local edits.

## Repair installation

**Repair installation** can save a patch backup of tracked changes and restore the official application core without deleting models, shared caches, generated jobs or untracked user files.

Patch backups live under:

```text
~/.dublocal/repair-backups/
```

## Local services and paths

DubLocal listens only on:

```text
http://127.0.0.1:7861
```

Contextual translation may temporarily start a loopback-only llama-server on an ephemeral port.

Typical paths:

```text
~/dublocal/                         Git checkout
~/.dublocal/logs/                   launcher logs
~/.dublocal/repair-backups/         repair patches
~/.cache/huggingface/hub/           shared HF cache
~/Library/Caches/DubLocal/jobs/     generated/intermediate jobs
```

Exact app/model locations may use `platformdirs`.

The jobs cache is disposable: normal startup removes jobs older than 24 hours and caps it at 4 GiB. Persistent model assets and shared Hugging Face files are not part of this cleanup.

## Older-build recovery

Only if the in-app updater is too old to function:

```bash
cd ~/dublocal
git pull
zsh scripts/macos/install-launcher.sh
```

For normal maintenance use the in-app updater/repair flow.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) before deleting models or rebuilding the installation.
