# DubLocal troubleshooting

**Applies to v0.4.1.dev0 / M4 + M3.1 Contextual Translation.**

Most DubLocal failures belong to one layer. Fix that layer rather than reinstalling everything.

## DubLocal.app opens nothing

Use **Stop DubLocal.app**, reopen **DubLocal.app**, then choose **Stop All & Launch**.

Launcher log:

```text
~/.dublocal/logs/dublocal.log
```

If the managed environment is missing, rerun:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

## Generated SRT/WAV shows a Gradio file-access error

Update DubLocal and restart. Generated outputs must live under DubLocal's own jobs cache, which is explicitly allowed by the local Gradio runtime.

## YouTube HTTP 429

YouTube is temporarily rate-limiting caption/media delivery. DubLocal retries caption retrieval but does not evade the restriction.

Use **Transcribe locally** if captions remain blocked. If YouTube also refuses audio, wait or use a local copy you have the right to process.

# Transcription

## FFmpeg / ffprobe / whisper.cpp missing

Check **Settings → Local Resources** first.

The macOS installer can offer Homebrew packages for missing media/transcription tools. Whisper models are separate from the `whisper-cli` executable and live under **Settings → Model Manager → Whisper**.

## Whisper checksum failure

DubLocal rejects a model whose checksum does not match the registered upstream hash. Retry the install; do not force an unknown/partial file into place.

## Transcription is slow

Tiny prioritizes speed, Base is the normal starting point, and Small trades more time/storage for accuracy. Apple Silicon normally benefits from whisper.cpp's Metal path; Intel uses CPU.

# Contextual translation — recommended

## “Contextual translation is not prepared”

Open:

**Settings → Model Manager → Contextual translation · Qwen3 4B → Prepare / verify contextual translation**

DubLocal will reuse an existing `llama.cpp` command if possible. Otherwise it can install `llama.cpp` through Homebrew, then download/register the pinned ~2.5 GB Qwen3 model in the shared Hugging Face cache.

## Model download is large

That is expected for Contextual quality. The Q4_K_M GGUF is about 2.5 GB and is downloaded only once when explicitly prepared. The shared Hugging Face cache is used so another compatible local application can reuse the same snapshot.

If storage matters more than quality, choose **Fast legacy · OPUS** explicitly instead.

## Qwen checksum failure

DubLocal pins an immutable upstream revision and SHA-256. If the file hash does not match, it is not registered.

Do not bypass this check. A repeatable mismatch means the registry/upstream state needs review.

## `llama.cpp` missing after preparation

Check **Settings → Local Resources**. The panel should show `llama-cli` or `llama ... cli`.

If Homebrew reports success but the app still does not see the executable, restart DubLocal and rescan resources. If it remains missing, include the exact Model Manager error when reporting the problem.

## Contextual translation is slower than OPUS

Expected. Qwen3 is doing generative translation with context instead of a small sentence-level Marian pass.

The quality mode is optimized for dialogue coherence rather than minimum latency. OPUS remains available when speed is the priority.

## Why does a long movie use more memory/context?

This is intentional. In v0.4.1.dev0 the input context budget grows with programme duration from roughly 4,096 tokens toward a 24,576-token cap.

The model does not receive the entire movie repeatedly. DubLocal combines:

- nearby source dialogue;
- sampled programme-wide dialogue;
- recent translated lines as rolling memory.

The status box shows the active budget before translation starts.

## Translation output is missing/duplicated/misaligned

Contextual translation uses constrained JSON with subtitle IDs. DubLocal validates that every target ID appears exactly once.

If this validation fails, the job stops rather than writing a shifted subtitle file. Report the exact error; do not switch off alignment checks.

## Translation is still awkward

Context greatly improves the information available to the model, but local machine translation is not guaranteed to equal a professional human translator.

Review the side-by-side preview before generating speech or publishing subtitles. If a consistent failure occurs, save a small lawful example of the source/translation and report it; it can be used to improve prompting/context planning.

# Fast legacy OPUS

## Why does OPUS produce literal or strange dialogue?

The legacy engine translates subtitle texts sentence-by-sentence. That is the reason it is no longer the default quality mode.

Use **Contextual quality** for normal dialogue work. Keep OPUS for quick/low-storage jobs.

## OPUS model missing

Use **Settings → Model Manager → Fast legacy translation · OPUS** and install the required direction(s). Non-English ↔ non-English uses two local passes through English.

# Kokoro / M4

## Another app has Kokoro but DubLocal does not detect it

Use **Settings → Local Resources → Rescan local resources** after updating. A reusable environment must expose `kokoro`, NumPy, PyTorch and Hugging Face Hub.

DubLocal does not import another application's `site-packages`; it invokes that environment's Python as an isolated worker.

## Kokoro language unsupported

Official Kokoro coverage exposed by DubLocal includes American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Hungarian, Russian and German can be translated but are not official Kokoro voice languages. This is a TTS limitation, not a translation failure.

## Voice lines overlap

M4 preserves subtitle start times and reports overruns rather than silently altering timing. M5 adds duration fitting. Overlap in the M4 voice-only preview is diagnostic, not final dubbing behavior.

# Updates / repair

## Updater reports modified tracked files

Normal update refuses to overwrite them. Use **Repair installation** only when the edits are accidental or the installation needs recovery. DubLocal saves a patch backup first when replacement is authorized.

Backups:

```text
~/.dublocal/repair-backups/
```

## Branch is ahead/diverged

Automatic update/repair will not rewrite local Git history. This needs manual Git review.

## Update installed but UI is old

Click **Restart DubLocal**. If necessary reopen the launcher and choose **Stop All & Launch**.

## Still stuck?

Provide:

- exact text from the nearest DubLocal status box;
- source type (YouTube/local);
- action clicked immediately before the error;
- launcher log tail only for startup/launcher failures.

Do not post account cookies, authentication tokens, copyrighted media you cannot share, or private paths you do not want public.
