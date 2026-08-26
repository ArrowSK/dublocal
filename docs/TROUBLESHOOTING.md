# DubLocal troubleshooting

Most DubLocal problems belong to one layer: launcher, source access, subtitles, Whisper, translation or updates. Fix the layer that failed; do not delete the whole installation unless there is evidence the whole environment is damaged.

## DubLocal.app opens nothing

First use **Stop DubLocal.app**, then reopen **DubLocal.app** and choose **Stop All & Launch**.

The launcher log is:

```text
~/.dublocal/logs/dublocal.log
```

If the log says the Python environment is missing, rerun the installer from the repository:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

## A generated SRT shows a Gradio file-access error

DubLocal-generated files should live under DubLocal's own jobs cache, which the launcher explicitly exposes to the local Gradio server.

If an older build shows a red Gradio `Error` block after successful transcription, update DubLocal and restart it. This exact compatibility issue was fixed by allowing only DubLocal's generated jobs directory rather than broad user folders.

## YouTube returns HTTP 429

`429 Too Many Requests` means YouTube is temporarily rate-limiting the request.

For caption requests, DubLocal retries with backoff. If YouTube still refuses the captions, use **Transcribe locally** instead. That fallback requests audio only after you explicitly start it.

If YouTube also rate-limits media delivery, DubLocal will not try to evade the restriction. Wait and retry later or use a local copy you are allowed to process.

## FFmpeg or ffprobe is missing

Local media inspection, subtitle normalization and Whisper audio preparation need FFmpeg.

Rerun:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

If Homebrew is present, the installer can offer `brew install ffmpeg`.

## whisper.cpp engine missing

The Whisper status box will say the engine is missing if `whisper-cli` cannot be found.

Rerun the launcher installer and allow the optional whisper.cpp installation. On Homebrew systems this is the `whisper-cpp` package.

## Whisper model missing

This is different from the engine being missing. The engine can be installed while no AI weights are installed.

In **Local transcription · Whisper**, choose a model and click **Install / verify model**. Base is the recommended first model.

## Whisper model checksum fails

DubLocal deletes a downloaded Whisper model if its checksum does not match the expected upstream hash. Do not rename or force the partial file into place.

Retry later. If the failure is repeatable, the upstream file may have changed and DubLocal's model registry should be reviewed before accepting it.

## Transcription is slow

Long movies take time, especially with larger models.

Apple Silicon normally uses whisper.cpp's Metal path. Intel Macs deliberately use a conservative CPU path. Tiny is the speed-first Whisper option; Base is the normal starting point; Small trades more time and storage for accuracy.

## Subtitle language says Auto detect after extraction

DubLocal can infer the language only when the caption/embedded stream provides a language code that maps to the M3 allowlist.

If **Local translation → Subtitle language** remains **Auto detect**, choose the correct language manually before preparing translation. Translation will not guess an unknown source language silently.

## “Local translation is not prepared yet”

Translation dependencies are optional by design. Choose the source and target languages, then click **Prepare translation**.

On first use, DubLocal installs its optional local translation Python stack and downloads only the OPUS model route required for the selected languages.

If the status says the packages were installed but the running process cannot see them yet, use **Restart DubLocal** once, reopen the same media/subtitle workflow, and click **Prepare translation** again.

## Translation model missing

The status panel shows two model roles:

```text
Many languages → English
English → many languages
```

English ↔ another supported language needs one of them. Translation between two non-English languages uses both because M3 pivots locally through English.

Click **Prepare translation** with the desired source/target pair. DubLocal installs only the model(s) that route requires.

## Translation model download or checksum fails

M3 downloads pinned safetensors revisions and verifies the ~310 MiB weight file with SHA-256.

If the checksum fails, DubLocal deletes that model folder instead of loading it. Retry the download. A repeatable mismatch should be treated as an upstream/model-registry change, not bypassed.

## Translation is slow or briefly uses high memory

The OPUS models are local neural translation models. DubLocal loads the required model for a translation pass and releases it afterward.

On Apple Silicon, PyTorch uses MPS when available. If a Marian operation is unsupported on MPS, DubLocal falls back to CPU rather than failing the whole translation. A non-English → non-English translation also runs two model passes, so it is naturally slower than an English ↔ other-language route.

## Translation quality is awkward

M3 is deliberately a lightweight local baseline, not a claim of human-level literary translation. Each subtitle segment is translated while its timing boundary stays fixed, which is useful for dubbing alignment but gives the model less cross-scene context.

Do not change timestamps merely to improve wording. A later subtitle editor milestone can support manual text correction while preserving the source timing model.

## The in-app updater says local changes were detected

This is a safety stop, not an updater failure. DubLocal will not overwrite a dirty Git checkout.

If you intentionally edited the source, review those changes with Git before updating. If you did not intend to edit anything, inspect the reported repository rather than using a force/reset command blindly.

The installer no longer changes executable bits on tracked scripts, so a normal modern install should not dirty the repository.

## The updater says the branch diverged or is ahead of GitHub

Automatic update is disabled because your checkout contains history that a fast-forward cannot safely replace.

That is a developer/Git state and needs manual review. DubLocal intentionally does not merge, rebase or discard commits automatically.

## Update installed, but the UI still looks old

Click **Restart DubLocal** after installing an update. If an older process is still responding, launch `DubLocal.app` and choose **Stop All & Launch**.

## I removed a model by mistake

Nothing else is damaged. Whisper and translation models are stored separately from the application code. Choose the model/route again and reinstall it from the relevant panel.

## Still stuck?

When reporting a problem, the most useful information is:

- the exact text in DubLocal's status box;
- whether the source is YouTube or a local file;
- which action you clicked immediately before the error;
- for launcher/startup problems only, the relevant tail of `~/.dublocal/logs/dublocal.log`.

Avoid posting copyrighted media, private file paths you do not want public, account cookies or authentication tokens in a GitHub issue.
