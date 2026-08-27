# DubLocal troubleshooting

**Applies to v0.4.2.dev0 / Subtitle Export + Translation Quality Pass.**

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

DubLocal puts transcription WAVs, temporary YouTube audio, generated SRTs, per-job TTS files, llama-server logs and other intermediate job artifacts in the macOS cache, not in the repository or Documents folder:

```text
~/Library/Caches/DubLocal/jobs/
```

They are temporary working files. On each normal DubLocal launch, stale job folders older than 24 hours are removed. The jobs cache is also capped at 4 GiB; if it is larger, the oldest remaining jobs are removed first.

Models are different: Whisper models, contextual-model registrations and the shared Hugging Face cache are intentionally persistent and are not touched by job-cache cleanup.

## YouTube HTTP 429

YouTube is temporarily rate-limiting caption/media delivery. DubLocal retries caption retrieval but does not evade the restriction.

Use **Transcribe locally** if captions remain blocked. If YouTube also refuses audio, wait or use a local copy you have the right to process.

# Transcription

## FFmpeg / ffprobe / whisper.cpp missing

Check **Settings → Local Resources** first.

The macOS installer can offer Homebrew packages for missing media/transcription tools. Whisper models are separate from the `whisper-cli` executable and live under **Settings → Model Manager → Whisper**.

## Whisper checksum failure

DubLocal rejects a model whose checksum does not match the registered upstream hash. Retry the install; do not force an unknown/partial file into place.

## Transcription is slow or inaccurate

Base prioritizes practicality. Small is stronger but slower. Accurate Large-v3-Turbo-Q5 is the preferred local source-quality option for songs, accents, noisy material or obviously damaged automatic captions.

Apple Silicon normally benefits from whisper.cpp's Metal path; Intel uses CPU.

# Contextual translation — Recommended for this Mac

## Why does my Mac show Lightweight, Balanced or Best quality?

DubLocal adapts the contextual translator to local architecture and physical memory.

Current defaults are:

```text
Apple Silicon < 12 GB     Qwen3 4B · review off · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · review off · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · 24k input cap
Intel < 24 GB             Qwen3 4B · review off · smaller context
Intel 24 GB+              Qwen3 8B · review off · reduced context
```

Open **Translation engine details** or **Settings → Model Manager → Contextual translation** to see the exact detected hardware, model, context budget and runtime allocation.

These are conservative recommendations, not hard statements that another model could never run.

## I have an 8 GB M1. Why is Qwen3 4B recommended?

Because model-file size is only part of memory use. macOS, model weights and llama.cpp's KV/context cache all share unified memory.

On this profile DubLocal therefore uses Qwen3 4B and reduces the actual llama.cpp context allocation. It does not start a 32k context and merely send a shorter prompt.

The goal is to avoid unnecessary swap/memory pressure while retaining contextual translation.

## I have a 16 GB M1/M2. Why is review off?

The 16 GB profile uses Qwen3 8B for the stronger first-pass translation but keeps the automatic second review pass off and caps context below the maximum. This is a quality/performance compromise rather than a compatibility limitation.

## “Contextual translation is not prepared”

Open:

**Settings → Model Manager → Contextual translation → Prepare / verify contextual translation**

DubLocal will detect the hardware profile, reuse/install `llama.cpp`, and download only the Qwen model recommended for that Mac.

Approximate contextual model sizes:

- Qwen3 4B Q4_K_M: 2.5 GB.
- Qwen3 8B Q4_K_M: 5.03 GB.

Both are checksum-verified before registration.

## I upgraded from a build that already downloaded another Qwen model

The Model Manager status shows the recommended model and whether the alternate contextual model is also registered.

Preparing contextual translation does not download both models. Removing contextual models removes DubLocal's 4B/8B registrations/links while keeping the underlying shared Hugging Face cache intact for other local applications.

## Qwen checksum failure

DubLocal pins immutable upstream revisions and checksums. If the downloaded file does not match, it is not registered.

Do not bypass this check. A repeatable mismatch means the registry/upstream state needs review.

## `llama.cpp` missing after preparation

Check **Settings → Local Resources**. The panel should show a llama.cpp executable.

If Homebrew reports success but DubLocal still does not see it, restart DubLocal and rescan resources. If it remains missing, include the exact Model Manager error when reporting the problem.

## Contextual translation is slower than OPUS

Expected. Qwen3 is doing generative translation with context rather than a small sentence-level Marian pass.

The hardware profile is designed to avoid absurd defaults, not make generative translation instant. OPUS remains available when speed/minimum storage is the priority.

## Translation output is missing/duplicated/misaligned

DubLocal preserves subtitle IDs and validates every contextual chunk. If a chunk is malformed it attempts contextual format/ID recovery; it does not silently weaken alignment checks.

If output still cannot be validated, the job stops rather than writing a shifted subtitle file. Report the exact visible error.

## Translation contains Chinese characters, untranslated English or runtime text

That output should now be rejected before the SRT is written for the current European target set.

DubLocal validates for:

- CJK/Hangul contamination;
- substantial wrong-script leakage;
- llama runtime/model/prompt text;
- protected caption tags such as `[MUSIC]`.

If such content appears in a current v0.4.2 translated SRT, report the smallest reproducible sample and the running version.

## Translation is still awkward

A larger model and better context improve the translation but do not guarantee professional-human output. Also check the **Original** column: damaged automatic captions can make a translation look wrong even when the translator is faithfully processing bad source text.

For obviously garbled source captions, use local Accurate Whisper transcription first.

# Fast legacy OPUS

## Why does OPUS produce literal or strange dialogue?

The legacy engine translates subtitle texts sentence-by-sentence. Keep it for quick/minimum-storage jobs; use **Recommended for this Mac** for contextual dialogue translation.

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
- detected contextual hardware/profile if translation is involved;
- launcher log tail only for startup/launcher failures.

Do not post account cookies, authentication tokens, copyrighted media you cannot share, or private paths you do not want public.
