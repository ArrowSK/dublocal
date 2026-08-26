# DubLocal user guide

**Current development build: v0.3.0.dev0 — M3 Local Translation**

DubLocal is meant to feel like a small Mac utility, not a Python project. Once installed, start it with **DubLocal.app** and use the local browser window it opens.

This guide covers what the current M3 build actually does: source/caption discovery, local Whisper transcription, local subtitle translation, in-app updating/repair and reuse of compatible local dependencies.

> There is no packaged GitHub Release yet. `v0.3.0.dev0` is the current development build on `main`. See [CHANGELOG.md](../CHANGELOG.md) for the build history.

## Before you start

Local video/audio files are not uploaded to a cloud transcription or translation service. Whisper and OPUS translation run on your Mac.

YouTube is different because the source itself is remote: DubLocal has to contact YouTube to inspect the video, request captions, or fetch audio when you explicitly start local transcription. Process only media you have the right or legal authority to use.

## 1. Choose the source

At the top choose **YouTube** or **Local file**.

For YouTube, paste one video URL and click **Scan source**. DubLocal shows the title and any creator/automatic caption tracks it can discover.

For a local file, select the media and click **Scan source**. DubLocal uses your existing local `ffprobe` installation to inspect the streams and list embedded subtitle tracks.

## 2. Get timed source subtitles

You can either reuse existing captions or make new ones from the audio.

### Existing subtitles

Choose the subtitle/caption track, confirm that you have the right to process the media, then click **Extract existing subtitles**.

DubLocal normalizes supported text captions to SRT. That SRT becomes the common timeline used by translation and, later, dubbing.

Image-only subtitle formats such as PGS are not silently OCR'd. Use local transcription for those.

### Local Whisper transcription

Open **Local transcription · Whisper**.

The status box shows whether `whisper.cpp` is ready and which Whisper models are installed.

| Model | Approximate size | Best use |
| --- | ---: | --- |
| Tiny | 75 MiB | quick tests / speed first |
| Base | 142 MiB | recommended starting point |
| Small | 466 MiB | better accuracy when extra time/storage is acceptable |

If a model is missing, click **Install / verify model**. DubLocal downloads it only because you asked and verifies its checksum before use.

Choose the spoken language or leave **Auto detect**, then click **Transcribe locally**. FFmpeg prepares 16 kHz mono audio and `whisper.cpp` creates the timestamped SRT locally.

When Auto detect is used, DubLocal carries Whisper's detected language into the translation section where possible.

## 3. Translate locally

After extraction or transcription, open **Local translation**.

Choose **Subtitle language** and **Translate to**. The source language is normally filled from the caption metadata or Whisper's detected language; if it is unknown, choose it manually.

DubLocal shows the route it will use, for example:

```text
English → Hungarian
Hungarian → English
Hungarian → English → German
```

The last route means that two non-English languages are translated locally through English.

### Prepare translation

Click **Prepare translation** the first time a route needs resources.

DubLocal follows a **reuse first, install second** policy:

- if the needed Python translation stack already exists in DubLocal's own environment, it uses it;
- if a compatible stack exists in a recognized external environment (for example another local AI application), DubLocal can use that Python through an isolated worker process rather than copying its packages into DubLocal;
- OPUS model snapshots use the normal shared Hugging Face cache, so the exact pinned model can be reused if another compatible app has already downloaded it;
- only missing resources are obtained.

The two current OPUS models are Apache-2.0 and roughly 310 MiB each. Exact revisions and SHA-256 values are recorded in `MODEL_LICENSES.json`.

DubLocal never injects one virtual environment's `site-packages` into another. That would be fragile. Cross-application runtime reuse happens only through a separate process with a narrow input/output contract.

### Translate

Click **Translate subtitles**.

The output preview shows the original and translated text side by side. The timestamps are preserved exactly, and **Translated SRT** gives you the translated file.

On Apple Silicon, the translation stack can use MPS when the required operations are supported and fall back to CPU if necessary.

There is no silent cloud translation fallback.

### Removing translation models

**Remove translation models** removes DubLocal's registration/link (or an older private DubLocal copy). It deliberately does **not** delete an underlying shared Hugging Face cache snapshot, because another local application may still rely on it.

## Reusable local resources

Open **Reusable local resources** to see what DubLocal found on the Mac.

The panel currently reports:

- FFmpeg and ffprobe;
- `whisper-cli`;
- the shared Hugging Face cache location;
- a compatible Kokoro Python runtime if one is found in a known local environment.

Kokoro voice generation itself arrives in M4. The point of detecting it now is to avoid building M4 around the assumption that every application must install a second copy of the same heavy stack.

## YouTube HTTP 429

YouTube can temporarily rate-limit caption or media delivery. DubLocal retries normal caption delivery but does not try to evade the restriction.

If captions remain blocked, use **Transcribe locally**. If YouTube also refuses audio delivery, wait and retry later or use a local copy you are allowed to process.

## Updating DubLocal

Open **DubLocal updates & repair**.

For a normal clean installation:

**Check for updates → Install update → Restart DubLocal**

The status now shows three separate identities: the running DubLocal version, the local Git checkout and official GitHub `main`. This catches the common case where files have updated but the running environment is stale.

Normal update rules are intentionally strict:

- only `ArrowSK/dublocal` `main` is trusted automatically;
- clean fast-forward updates are allowed;
- tracked local edits are never overwritten by a normal update;
- local commits or diverged history are not rewritten automatically.

## Repair installation

Use **Repair installation** when the updater reports that the checkout/runtime is inconsistent, or tracked DubLocal program files have been modified.

If tracked program files must be replaced, tick the repair confirmation. DubLocal then:

1. saves the current tracked-file diff as a patch in `~/.dublocal/repair-backups/`;
2. restores official tracked program files from GitHub `main`;
3. refreshes the managed Python core;
4. verifies that DubLocal imports from the expected checkout and reports the expected version;
5. schedules a clean restart.

Repair does **not** delete Whisper/translation models, the shared Hugging Face cache, generated jobs or untracked user files. It also refuses to rewrite local commits/diverged Git history.

## What M3 does not do yet

M3 stops at synchronized source and translated subtitle files. It does not yet synthesize the translated voice track.

M4 is the local Kokoro TTS milestone. It will build on the reusable-runtime mechanism above so that a compatible Kokoro installation already present on the Mac can be used through an isolated worker instead of needlessly installed again.

Later milestones add timing adaptation, original-audio ducking, preview and final video rendering.

## If something goes wrong

Do not reinstall everything immediately. Read the nearest status panel first. DubLocal tries to keep source access, captions, Whisper, translation, dependency reuse, updater and launcher failures separate.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for practical recovery steps.
