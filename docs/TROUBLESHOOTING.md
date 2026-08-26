# DubLocal troubleshooting

**Applies to current development build v0.3.0.dev0 / M3.** See [CHANGELOG.md](../CHANGELOG.md) for build history.

Most DubLocal problems belong to one layer: launcher, source access, subtitles, Whisper, translation, reusable local resources, or updates/repair. Fix the layer that failed; do not delete the whole installation unless there is evidence the whole environment is damaged.

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

If an older build shows a red Gradio `Error` block after successful transcription, update DubLocal and restart it. This compatibility issue was fixed by allowing only DubLocal's generated jobs directory rather than broad user folders.

## YouTube returns HTTP 429

`429 Too Many Requests` means YouTube is temporarily rate-limiting the request.

For captions DubLocal retries with backoff. If YouTube still refuses them, use **Transcribe locally**. That fallback requests audio only after you explicitly start it.

If YouTube also rate-limits media delivery, DubLocal will not try to evade the restriction. Wait and retry later or use a local copy you are allowed to process.

## FFmpeg or ffprobe is missing

DubLocal reuses system/local FFmpeg rather than installing a private copy per feature. Open **Reusable local resources** to see what was detected.

If FFmpeg is missing, rerun:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

If Homebrew is present, the installer can offer `brew install ffmpeg`.

## whisper.cpp engine missing

The Whisper status box reports this separately from model availability. DubLocal reuses `whisper-cli` wherever the supported local paths expose it.

Rerun the launcher installer and allow the optional Homebrew `whisper-cpp` installation if no copy exists.

## Whisper model missing

The engine can be installed while no model weights are installed. In **Local transcription · Whisper**, select Tiny/Base/Small and click **Install / verify model**. Base is the normal starting point.

## Whisper model checksum fails

DubLocal deletes a downloaded Whisper model if its checksum differs from the expected upstream hash. Do not rename or force the partial file into place.

Retry later. A repeatable mismatch should be treated as an upstream/model-registry change and reviewed before accepting new weights.

## Transcription is slow

Long media takes time, especially with larger models. Apple Silicon normally uses whisper.cpp's Metal path. Intel Macs deliberately use a conservative CPU path.

Tiny is speed-first; Base is the normal balance; Small trades more time/storage for accuracy.

## Subtitle language says Auto detect after extraction

DubLocal can infer the language only when the stream/caption metadata maps to the current M3 allowlist.

If **Local translation → Subtitle language** stays **Auto detect**, choose the correct language manually. Translation deliberately does not guess an unknown source language.

## “Local translation is not prepared yet”

Open **Reusable local resources** first if you are curious what is already present. DubLocal now tries to reuse a compatible translation runtime from a known external local environment before installing another PyTorch/Transformers stack into its own venv.

If no compatible runtime exists, **Prepare translation** installs the optional stack into DubLocal's environment. If installation succeeds but the current process cannot see it immediately, restart DubLocal once and prepare again.

## Why doesn't DubLocal simply import packages from another app's venv?

Because Python virtual environments are dependency-isolation boundaries. Adding another application's `site-packages` to DubLocal's import path can combine incompatible Torch, Transformers or other library versions and break both applications.

Where reuse is supported, DubLocal starts the compatible external Python as a separate worker process. M3 translation already supports this. M4 Kokoro is designed to use the same mechanism.

## Translation model missing

The status panel shows two model roles:

```text
Many languages → English
English → many languages
```

English ↔ another supported language needs one; non-English ↔ non-English needs both because M3 pivots through English.

Click **Prepare translation** for the selected route.

## “Prepare translation” appears to download a model I already have

M3 uses the normal Hugging Face shared cache. If the **same repository and pinned revision** already exist in that cache, Hugging Face should reuse the local snapshot rather than download/store another full copy.

A similarly named model at a different revision is not treated as interchangeable because DubLocal verifies a specific weight SHA-256. Open **Reusable local resources** to see the shared cache path, and the translation status shows whether a registered model is using the shared HF cache or an older DubLocal-local copy.

## Translation model download or checksum fails

M3 uses pinned safetensors revisions and verifies the main weight file with SHA-256. A failed snapshot is not registered for use.

Do not bypass a repeatable checksum mismatch; it should be reviewed as an upstream/model-registry change.

## Removing a translation model did not free all disk space

That can be intentional. New M3 installs register models from the shared Hugging Face cache. **Remove translation models** removes DubLocal's registration/link, but does not delete the shared cache snapshot because another local application may rely on it.

Shared-cache cleanup should be handled separately and deliberately, not as a side effect of removing a model from DubLocal.

## Translation is slow or briefly uses high memory

The OPUS models are local neural translation models. DubLocal loads the required model for a pass and releases it afterward.

Apple Silicon can use MPS. If a Marian operation fails on MPS, DubLocal falls back to CPU. A non-English → non-English route performs two model passes and is therefore slower.

## Translation quality is awkward

M3 is a lightweight local baseline, not human literary translation. Subtitle segments are translated while their timing boundaries stay fixed, which is useful for later dubbing but gives the model limited cross-scene context.

Do not change timing just to improve wording. A later editor can support text correction while preserving the source timing model.

## The updater reports modified local program files

Normal update is intentionally blocked so your local tracked edits are not overwritten.

If those edits are accidental or the installation needs recovery, open **DubLocal updates & repair** and use **Repair installation**. When tracked program files need replacement, tick the confirmation first.

Repair saves the current tracked Git diff as a patch under:

```text
~/.dublocal/repair-backups/
```

It then restores official tracked program files from `ArrowSK/dublocal` `main`, refreshes the managed Python core, verifies the imported version/path and schedules a clean restart.

Models, shared caches, generated jobs and untracked files are not deleted by this repair path.

## The updater says the branch diverged or is ahead of GitHub

Automatic update **and repair** are disabled because the checkout contains Git history that DubLocal must not discard automatically.

This needs manual Git review. Repair does not use force-reset to erase local commits or resolve diverged history.

## Update check says current, but the running UI/version is old

The current updater compares the running package version with the local checkout version. If Git is already current but the managed Python core is stale, it reports a repair condition rather than incorrectly saying everything is healthy.

Use **Repair installation**; the core will be refreshed and import-checked before restart.

## Update installed, but the UI still looks old

Click **Restart DubLocal**. If an older process is still responding, launch `DubLocal.app` and choose **Stop All & Launch**.

## I removed a model by mistake

Nothing else is damaged. Choose the model/route again and prepare/install it from the relevant panel. For translation, a still-present shared Hugging Face snapshot can be reused.

## Still stuck?

When reporting a problem, the most useful information is:

- the exact text in DubLocal's nearest status box;
- whether the source is YouTube or a local file;
- which action you clicked immediately before the error;
- for launcher/startup problems only, the relevant tail of `~/.dublocal/logs/dublocal.log`.

Avoid posting copyrighted media, private file paths you do not want public, account cookies or authentication tokens in a GitHub issue.
