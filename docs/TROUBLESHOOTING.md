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

## Where do temporary media and generated files go?

DubLocal puts transcription WAVs, temporary YouTube audio, generated SRTs, subtitle-format exports, per-job TTS files and other intermediate job artifacts in the macOS cache, not in the repository or your Documents folder:

```text
~/Library/Caches/DubLocal/jobs/
```

They are temporary working files. On each normal DubLocal launch, stale job folders older than 24 hours are removed. The jobs cache is also capped at 4 GiB; if it is larger, the oldest remaining jobs are removed first. Files from the current session are not deleted while the app is running.

Models are different: Whisper models, registered contextual models and the shared Hugging Face cache are intentionally persistent and are not touched by job-cache cleanup.

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

## Song lyrics or noisy speech are transcribed incorrectly

Lyrics are materially harder than ordinary spoken dialogue. Repeated instrumentation, stylized pronunciation, backing vocals and compressed mixes can make Whisper Base produce plausible-looking but wrong words.

Before judging translation quality, inspect the source transcript. If it contains obvious errors, try **Whisper Small** and set the spoken language explicitly when known.

Contextual translation can resolve ambiguity, but it should not confidently invent lyrics that are absent from the source transcript.

## I only need subtitles, not translation

That is a complete workflow. After extraction/transcription, use the **Subtitle download** directly in **2 · Subtitles**.

SRT is the default. WebVTT, TXT and CSV are also available from the **Download format** selector. Changing formats reuses the existing timeline; Whisper does not run again.

# Contextual translation — recommended

## “Contextual translation is not prepared”

Open:

**Settings → Model Manager → Contextual translation · Qwen3 4B → Prepare / verify contextual translation**

DubLocal will reuse an existing `llama.cpp` installation if possible. Otherwise it can install `llama.cpp` through Homebrew, then download/register the pinned ~2.5 GB Qwen3 model in the shared Hugging Face cache.

## Model download is large

That is expected for Contextual quality. The Q4_K_M GGUF is about 2.5 GB and is downloaded only once when explicitly prepared. The shared Hugging Face cache is used so another compatible local application can reuse the same snapshot.

If storage matters more than quality, choose **Fast legacy · OPUS** explicitly instead.

## Qwen checksum failure

DubLocal pins an immutable upstream revision and SHA-256. If the file hash does not match, it is not registered.

Do not bypass this check. A repeatable mismatch means the registry/upstream state needs review.

## `llama.cpp` missing after preparation

Check **Settings → Local Resources**. Contextual translation uses `llama-server`; the panel should show that executable. `llama-cli` is also reported because it is part of the same local installation.

If Homebrew reports success but the app still does not see `llama-server`, restart DubLocal and rescan resources. If it remains missing, include the exact Model Manager error when reporting the problem.

## Contextual translation is slower than OPUS

Expected, within reason. Qwen3 is doing generative translation with context instead of a small sentence-level Marian pass.

DubLocal loads the model once per translation job into a local `llama-server` and reuses that process for every chunk/recovery request. Short material is packed into fewer chunks when safe. This removes the previous repeated-model-load overhead, but a 4B generative model will still be slower than OPUS.

## Why does a long movie use more memory/context?

This is intentional. In v0.4.1.dev0 the input context budget grows with programme duration from roughly 4,096 tokens toward a 24,576-token cap.

The model does not receive the entire movie repeatedly. DubLocal combines:

- nearby source dialogue;
- sampled programme-wide dialogue;
- recent translated lines as rolling memory.

The status box shows the active budget before translation starts.

## Translation output is missing/duplicated/misaligned

Contextual translation uses a strict DubLocal marker + subtitle-ID line protocol. The model response must contain every expected subtitle ID exactly once before an SRT is written.

If an otherwise clean response omits one or more IDs, DubLocal preserves the valid lines and retries only the missing subtitle(s), still with the full original contextual prompt. It does not silently shift timestamps or substitute another translation engine.

If the missing IDs still cannot be recovered, the job stops rather than writing a corrupted subtitle file.

## `Loading model...`, prompt text or terminal garbage appears inside a translation

That is invalid output and should not occur after the current v0.4.1.dev0 reliability update.

Contextual translation now talks to a local `llama-server` HTTP API and reads only the assistant-response field. Server startup logs are discarded separately. The response is then accepted only if it matches the DubLocal marker/ID protocol.

If runtime banners or prompt echoes appear in a newly generated translation after updating and restarting, report that exact output as a bug; do not use the resulting SRT.

## Translation is still awkward

First compare the translation against the **Original** column. If the original source text is already wrong, improve transcription first.

If the original is correct but Qwen still produces an inaccurate or unnatural translation, that is a translation-model/prompt quality issue. Context substantially improves the information available to the model, but a 4B local model is not guaranteed to equal a professional human translator.

Review the side-by-side preview before generating speech or publishing subtitles. A small lawful source/translation example is particularly useful for improving prompting and context planning.

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
