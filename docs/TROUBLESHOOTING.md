# DubLocal troubleshooting

**Applies to current development build v0.4.0.dev0 / M4.** See [CHANGELOG.md](../CHANGELOG.md) for build history.

Most DubLocal problems belong to one layer: launcher, source access, subtitles, Whisper, translation, Kokoro, reusable local resources, or updates/repair. Fix the layer that failed; do not delete the whole installation unless there is evidence the whole environment is damaged.

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

## A generated SRT/WAV shows a Gradio file-access error

DubLocal-generated files should live under DubLocal's own jobs cache, which the launcher explicitly exposes to the local Gradio server.

If an old build shows a red Gradio `Error` block after successful generation, update DubLocal and restart it.

## YouTube returns HTTP 429

`429 Too Many Requests` means YouTube is temporarily rate-limiting the request.

For captions DubLocal retries with backoff. If YouTube still refuses them, use **Transcribe locally**. That fallback requests audio only after you explicitly start it.

If YouTube also rate-limits media delivery, DubLocal will not try to evade the restriction. Wait and retry later or use a local copy you are allowed to process.

## FFmpeg or ffprobe is missing

Open **Settings → Local Resources** to see what was detected.

If FFmpeg is missing, rerun:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

If Homebrew is present, the installer can offer `brew install ffmpeg`.

## whisper.cpp engine missing

The Whisper status box reports this separately from model availability. DubLocal reuses `whisper-cli` wherever the supported local paths expose it.

Rerun the launcher installer and allow the optional Homebrew `whisper-cpp` installation if no copy exists.

## Whisper model missing or checksum fails

Use **Settings → Model Manager → Whisper**. Choose Tiny/Base/Small and click **Install / verify model**.

DubLocal deletes a downloaded Whisper model if its checksum differs from the expected upstream hash. Do not rename or force a partial file into place.

## Transcription is slow

Long media takes time, especially with larger models. Apple Silicon normally uses whisper.cpp's Metal path. Intel Macs deliberately use a conservative CPU path.

Tiny is speed-first; Base is the normal balance; Small trades more time/storage for accuracy.

## Subtitle language stays Auto detect

DubLocal can infer the language only when stream/caption/Whisper metadata maps to the current allowlist.

If **Main → Local translation → Subtitle language** remains **Auto detect**, choose the correct language manually. Translation deliberately does not guess an unknown source language.

## “Local translation is not prepared yet”

Open **Settings → Local Resources** if you want to see what is already available, then use **Settings → Model Manager → OPUS · subtitle translation**.

DubLocal first looks for a compatible external translation runtime. If none exists, preparing translation installs the optional stack into DubLocal's environment.

## Translation model missing / duplicate download concern

The two current model roles are:

```text
Many languages → English
English → many languages
```

English ↔ another supported language needs one. Non-English ↔ non-English needs both because the route pivots through English.

OPUS models use the normal Hugging Face shared cache. If the exact repository/revision snapshot already exists, it is reused instead of storing another full copy.

Removing a translation model removes DubLocal's registration/private legacy copy but deliberately does not erase the shared HF snapshot.

## Translation model checksum fails

M3/M4 translation uses pinned safetensors revisions and verifies the main weight file with SHA-256. A failed snapshot is not registered for use.

Do not bypass a repeatable mismatch; it should be reviewed as an upstream/model-registry change.

## Translation is slow or awkward

The OPUS models are a lightweight local baseline, not human literary translation. Non-English → non-English uses two passes and is slower.

Subtitle boundaries stay fixed. That is deliberate because later voice/timing stages depend on a stable timeline.

# Kokoro / M4

## Local Resources says Kokoro is not detected, but another app has Kokoro

M4 fixes a macOS virtualenv-discovery bug where `venv/bin/python` symlinks could be resolved to the same framework Python and different venvs were accidentally treated as one environment.

After updating to M4, use **Settings → Local Resources → Rescan local resources**.

A compatible environment must provide all of:

```text
kokoro
numpy
torch
huggingface_hub
```

DubLocal checks known local project/venv locations and optional configured external Python paths. It does not import another app's `site-packages` directly.

## Why doesn't DubLocal simply import packages from another app's venv?

Because Python virtual environments are dependency-isolation boundaries. Mixing Torch/Kokoro/Transformers packages from another venv can destabilize both applications.

DubLocal instead runs the compatible external Python as a separate worker process. The worker receives a small JSON request, writes local WAV files/results, and exits.

## “Kokoro is not prepared yet”

Open **Settings → Model Manager → Kokoro · voice generation**.

Choose a language/voice and click **Prepare / verify Kokoro**.

DubLocal first reuses a compatible existing runtime. Only if none exists does it install the optional Kokoro extra into DubLocal's own venv.

Preparing may download missing official model/voice assets into the shared Hugging Face cache.

## Kokoro says the language is unsupported

That is intentional rather than a bug. Official Kokoro exposed in M4 supports:

- American/British English;
- Spanish;
- French;
- Hindi;
- Italian;
- Japanese;
- Brazilian Portuguese;
- Mandarin Chinese.

Hungarian, Russian and German can be translated by OPUS but are not official Kokoro languages. DubLocal will not silently use the wrong pronunciation frontend.

## Portuguese became Brazilian Portuguese

Kokoro's official Portuguese frontend is Brazilian Portuguese (`pt-BR`). M4 makes that explicit. Generic Portuguese translation remains a subtitle capability; voice generation is labelled **Portuguese · Brazil**.

## Kokoro generation is slow on first use

The first preparation/generation can be slower because the runtime loads PyTorch/Kokoro and may fetch missing model/voice assets into the shared HF cache.

Apple Silicon can use MPS. If the Kokoro/PyTorch combination exposes MPS but an operation fails, the worker retries on CPU rather than crashing the whole DubLocal process.

## Some voice lines overlap in the M4 WAV

M4 preserves every subtitle **start time**. It does not yet speed up, shorten or rewrite long synthetic speech.

If a generated line is longer than its subtitle window, the **Generated voice timeline** table shows an overrun such as `+0.85s`. When two lines overlap, the M4 voice-only preview mixes them instead of shifting the later subtitle off its timestamp.

M5 adds duration fitting. This overlap is therefore diagnostic information, not the final dubbing behavior.

## Why is the M4 output voice-only?

M4 is the TTS milestone. It deliberately does not alter the source soundtrack.

M5 adds original-audio ducking/mixing and stream-copy media output. Compatible video will not be re-encoded just because DubLocal adds/replaces audio.

# Updates / repair

## The updater reports modified local program files

Normal update is blocked so your local tracked edits are not overwritten.

Use **Settings → Updates → Repair installation** only when those edits are accidental or the installation needs recovery. If tracked files need replacement, tick the confirmation first.

Repair saves the current tracked Git diff under:

```text
~/.dublocal/repair-backups/
```

It restores official tracked program files, refreshes the managed Python core, verifies the imported version/path and schedules a clean restart. Models, shared caches, generated jobs and untracked files are not deleted.

## The updater says the branch diverged or is ahead of GitHub

Automatic update and repair are disabled because the checkout contains Git history DubLocal must not discard automatically.

This needs manual Git review. Repair does not force-reset local commits.

## Update check says current, but the running UI/version is old

Use **Settings → Updates → Repair installation**. The updater compares the running package with the local checkout and can repair a stale managed Python core.

## Update installed, but the UI still looks old

Click **Restart DubLocal**. If an older process is still responding, launch `DubLocal.app` and choose **Stop All & Launch**.

## Still stuck?

When reporting a problem, the most useful information is:

- the exact text in DubLocal's nearest status box;
- whether the source is YouTube or a local file;
- which action you clicked immediately before the error;
- for launcher/startup problems only, the relevant tail of `~/.dublocal/logs/dublocal.log`.

Avoid posting copyrighted media, private file paths you do not want public, account cookies or authentication tokens in a GitHub issue.
