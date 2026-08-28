# Installing DubLocal on macOS

**Current development build: v0.6.0.dev0 — Magic Flow UX**

DubLocal currently runs from a Git checkout, but after first setup ordinary use is through the native **DubLocal.app** launcher. Updates, repair and optional models are managed inside the app.

There is no packaged DMG/GitHub Release yet.

## Requirements

- macOS 13+
- Apple Silicon or Intel
- Python 3.11+; the installer can bootstrap a compatible Python
- FFmpeg/ffprobe
- optional whisper.cpp, llama.cpp and AI model weights depending on the features you use

DubLocal is designed to remain usable on M1-class Macs. Model recommendations and contextual allocations scale to memory rather than assuming a recent high-RAM machine.

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

The installer can offer Homebrew installation for required native tools. Heavy optional AI models are not silently bundled or downloaded.

## First launch

Open **DubLocal.app**. The top of Main is **Magic Flow**, which is the recommended starting point:

1. choose YouTube or Local file;
2. provide the link/file;
3. confirm rights/legal authority;
4. choose output language;
5. choose the outputs you want;
6. run Magic Flow.

Magic Flow uses resources that are already installed. If it needs a local model that is not ready, it stops with a clear Model Manager instruction rather than downloading hundreds of megabytes without asking.

The detailed Source → Subtitles → Translate → Voice-over → Export workflow remains below Magic Flow.

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

**Base · 142 MiB** is the practical normal starting model.

**Accurate · Large v3 Turbo Q5 · 547 MiB** is the stronger option for songs, accents and difficult/noisy audio. When it is already installed, Magic Flow can prefer it over automatic YouTube captions.

The tiny whisper.cpp Silero VAD asset may be prepared on demand for supported speech-oriented paths. The Accurate music profile has separate no-context/repetition protection and targeted two-pass recovery for suspicious sparse/gap regions.

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

Kokoro does not support every translation language. Magic Flow will still produce subtitles/translation when possible and will clearly explain when the requested voice stage needs a supported language/backend.

## In-app updates

Use:

**Settings → Updates → Check for updates → Install update → Restart DubLocal**

The updater compares the current checkout/running revision to official `main`, not just the displayed development version.

If local files have drifted, use **Repair installation** rather than deleting the repository or virtual environment manually.

## Temporary files

Working job data lives under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes jobs older than 24 hours and caps temporary job data at 4 GiB. Persistent AI models and shared Hugging Face assets are not deleted by this cleanup.

## M1-class compatibility

Current reliability and UX work does not add another heavy mandatory model:

- timing and soundtrack balance are FFmpeg DSP;
- subtitle packaging is remuxing;
- targeted ASR recovery reuses the selected Whisper model only for short suspicious ranges;
- low-memory Macs have stricter recovery/context caps;
- Magic Flow never silently prepares every optional model.

An M1 may take longer than newer hardware, but the workflow is intentionally designed to degrade by speed/profile rather than becoming unsupported.
