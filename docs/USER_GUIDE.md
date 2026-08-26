# DubLocal user guide

**Current development build: v0.4.0.dev0 — M4 Local Voice**

DubLocal is meant to feel like a small Mac utility, not a Python project. Once installed, start it with **DubLocal.app** and use the local browser window it opens.

The interface has two top-level areas:

- **Main** — process the current video/audio job.
- **Settings** — maintain DubLocal itself and optional local AI resources.

Inside **Settings** there are three subtabs: **Updates**, **Model Manager**, and **Local Resources**.

> There is no packaged GitHub Release yet. `v0.4.0.dev0` is the current M4 development build. See [CHANGELOG.md](../CHANGELOG.md) for the build history.

## Before you start

Local video/audio files are not uploaded to a cloud transcription, translation or TTS service. Whisper, OPUS and Kokoro run locally.

YouTube is different because the source itself is remote: DubLocal has to contact YouTube to inspect the video, request captions, or fetch audio when you explicitly start local transcription. Process only media you have the right or legal authority to use.

# Main

## 1. Choose the source

Choose **YouTube** or **Local file**.

For YouTube, paste one video URL and click **Scan source**. DubLocal shows the title and any creator/automatic caption tracks it can discover.

For a local file, select the media and click **Scan source**. DubLocal uses `ffprobe` to inspect its streams and list embedded subtitle tracks.

## 2. Get timed source subtitles

You can either reuse existing captions or make new ones from the audio.

### Existing subtitles

Choose the subtitle/caption track, confirm that you have the right to process the media, then click **Extract existing subtitles**.

DubLocal normalizes supported text captions to SRT. That SRT becomes the common timeline used by translation and voice generation.

Image-only subtitle formats such as PGS are not silently OCR'd. Use local transcription for those.

### Local Whisper transcription

Open **Local transcription · Whisper** on Main.

Choose the Whisper model and spoken language, then click **Transcribe locally**.

Model installation/removal lives in **Settings → Model Manager → Whisper**.

| Model | Approximate size | Best use |
| --- | ---: | --- |
| Tiny | 75 MiB | quick tests / speed first |
| Base | 142 MiB | recommended starting point |
| Small | 466 MiB | better accuracy when extra time/storage is acceptable |

FFmpeg prepares 16 kHz mono audio and `whisper.cpp` creates the timestamped SRT locally. With **Auto detect**, Whisper's detected language is carried into translation where possible.

## 3. Translate locally

After extraction or transcription, open **Local translation** on Main.

Choose **Subtitle language** and **Translate to**, then click **Translate subtitles**.

Possible local routes include:

```text
English → Hungarian
Hungarian → English
Hungarian → English → German
```

The last route means that two non-English languages are translated locally through English.

If the required model is not installed, use **Settings → Model Manager → OPUS · subtitle translation**.

The output preview shows original and translated text side by side. Timestamps are preserved exactly, and **Translated SRT** gives you the translated file.

There is no silent cloud translation fallback.

## 4. Generate a local voice track

Open **Local voice · Kokoro** on Main.

Choose **Voice source**:

- **Translated subtitles** — speak the translated SRT.
- **Source subtitles** — speak the original/extracted/transcribed SRT.

Then choose **Voice language**, **Kokoro voice**, and **Voice speed**, and click **Generate voice track**.

M4 creates:

- one local WAV for every subtitle segment;
- one synchronized voice-only WAV for the full timeline;
- a JSON generation manifest recording the runtime, model, voice, speed, timing and per-line durations;
- a table showing whether each generated line fits inside its current subtitle window.

The start time of every subtitle is preserved. If synthetic speech is longer than the subtitle window, DubLocal reports the overrun instead of silently speeding it up, cutting it or rewriting the text. That is intentional: M5 adds duration fitting.

The M4 WAV is **voice only**. It does not replace the original movie soundtrack yet.

### Kokoro language coverage

Official Kokoro support exposed in M4 is:

- American English;
- British English;
- Spanish;
- French;
- Hindi;
- Italian;
- Japanese;
- Brazilian Portuguese;
- Mandarin Chinese.

The translation engine supports additional targets such as Hungarian, Russian and German. Those can still produce translated SRT files, but official Kokoro cannot voice them. DubLocal does not silently route them through an incorrect pronunciation frontend.

For generic translated `Portuguese`, the Kokoro suggestion is explicitly **Brazilian Portuguese** (`pt-BR`).

# Settings

## Updates

Open **Settings → Updates**.

For a normal clean installation:

**Check for updates → Install update → Restart DubLocal**

The updater distinguishes the running DubLocal package, the local Git checkout, and official GitHub `main`.

Normal update rules are intentionally strict:

- only `ArrowSK/dublocal` `main` is trusted automatically;
- clean fast-forward updates are allowed;
- tracked local edits are never overwritten by a normal update;
- local commits or diverged history are not rewritten automatically.

### Repair installation

Use **Repair installation** when the checkout/runtime is inconsistent or tracked DubLocal program files were modified.

If tracked files need replacement, tick the repair confirmation first. DubLocal then saves a patch backup, restores official tracked files, refreshes the managed Python core, verifies the import/version, and schedules a clean restart.

Repair does **not** delete Whisper/translation/Kokoro cache assets, generated jobs or untracked user files.

## Model Manager

Open **Settings → Model Manager** to install, verify or prepare optional AI resources.

### Whisper

Choose Tiny, Base or Small and click **Install / verify model**. DubLocal downloads only the requested model and verifies its checksum.

### OPUS translation

Choose the model set that matches the kind of translation you need:

| Model set | What it enables | Approximate weights |
| --- | --- | ---: |
| English → supported languages | English subtitles into Hungarian/German/etc. | 310 MiB |
| Supported languages → English | Hungarian/German/etc. into English | 310 MiB |
| Non-English ↔ non-English | both directions through an English pivot | 620 MiB total |

Then click **Install / verify required model(s)**.

DubLocal follows a **reuse first, install second** policy. Compatible Python runtimes can be used through isolated worker processes, and exact OPUS snapshots are reused from the normal Hugging Face cache when already present.

### Kokoro

Open **Kokoro · voice generation**.

Choose the language/voice you expect to use and click **Prepare / verify Kokoro**.

DubLocal does this in order:

1. look for a compatible existing Kokoro Python environment;
2. if one exists, use its own Python executable through an isolated worker;
3. if none exists, install DubLocal's optional `kokoro` extra into the DubLocal venv;
4. instantiate the selected Kokoro frontend/voice to verify that the runtime and shared model assets are usable.

Preparing Kokoro may download missing official model/voice files into the normal shared Hugging Face cache. It does not copy another application's Python packages into DubLocal.

DubLocal also deliberately does not offer a broad **Uninstall Python dependencies** button for Kokoro: an external runtime is not owned by DubLocal, and shared dependencies/cache assets may be used by another local application.

## Local Resources

Open **Settings → Local Resources** to see what DubLocal can safely reuse on the Mac.

The panel reports:

- FFmpeg and ffprobe;
- `whisper-cli`;
- the shared Hugging Face cache location;
- a compatible Kokoro runtime when one is found.

### Why a real venv path matters

On macOS, `venv/bin/python` is often a symlink to the same framework Python used by several environments. Resolving that symlink can erase which venv the executable belongs to.

M4 therefore preserves the venv executable path itself. This lets DubLocal distinguish, for example, its own `.venv/bin/python` from another application's `.venv/bin/python`, even if both symlink to the same underlying framework binary.

Python virtual environments remain isolated. DubLocal never appends another application's `site-packages` into its own interpreter.

# YouTube HTTP 429

YouTube can temporarily rate-limit caption or media delivery. DubLocal retries ordinary caption delivery but does not try to evade the restriction.

If captions remain blocked, use **Transcribe locally**. If YouTube also refuses audio delivery, wait and retry later or use a local copy you are allowed to process.

# What M4 does not do yet

M4 stops at a synchronized voice-only WAV.

M5 adds:

- speech-duration fitting against subtitle windows;
- original-audio ducking/mixing;
- stream-copy media export when compatible;
- **Replace primary audio** as the default output mode;
- **Add dubbed audio as second track** as the optional multi-track mode.

Compatible video should not be re-encoded merely because a new audio stream is being created.

# If something goes wrong

Do not reinstall everything immediately. Read the nearest status panel first. DubLocal keeps source access, captions, Whisper, translation, Kokoro, dependency reuse, updater and launcher failures separate where possible.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for practical recovery steps.
