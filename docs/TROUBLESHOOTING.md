# DubLocal troubleshooting

**Applies to v0.4.2.dev0 — Subtitle Export + Translation Quality Pass.**

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

## Generated subtitle/WAV shows a Gradio file-access error

Update DubLocal and restart. Generated outputs must live under DubLocal's own jobs cache, which is explicitly allowed by the local Gradio runtime.

## Where do temporary files go?

Temporary YouTube audio, 16 kHz Whisper WAVs, generated/intermediate subtitles, per-job TTS files and llama-server logs live under:

```text
~/Library/Caches/DubLocal/jobs/
```

On normal startup, jobs older than 24 hours are removed. The job cache is capped at 4 GiB and prunes oldest jobs first when necessary.

Persistent models and the shared Hugging Face cache are intentionally outside this cleanup policy.

## YouTube HTTP 429

YouTube is temporarily rate-limiting caption/media delivery. DubLocal retries ordinary caption retrieval but does not evade the restriction.

Use **Transcribe locally** if captions remain blocked. If YouTube also refuses audio, wait or use a local copy you have the right to process.

# Subtitles / transcription

## I transcribed successfully but only want subtitles

That is supported directly in v0.4.2. The completed subtitle file appears in **2 · Subtitles**. Translation is optional.

Use the **Download format** selector for SRT (default), WebVTT or TXT. Changing format converts the current timeline; it does not run Whisper again.

## FFmpeg / ffprobe / whisper.cpp missing

Check **Settings → Local Resources** first.

The macOS installer can offer Homebrew packages for missing media/transcription tools. Whisper model weights are separate and live under **Settings → Model Manager → Whisper**.

## Which Whisper model should I use?

- Tiny: fastest, lowest accuracy.
- Base: normal default.
- Small: stronger but slower.
- Accurate Large-v3-Turbo-Q5: optional 547 MiB model intended for difficult audio, songs, accents or noisy material.

If a YouTube automatic caption track contains obvious nonsense, a stronger translation model is not the first fix. Re-transcribe the audio with Accurate Whisper so the translator receives a better source timeline.

## Whisper checksum failure

DubLocal rejects a model whose checksum does not match the registered upstream hash. Retry the install; do not force an unknown/partial file into place.

# Best-quality contextual translation

## “High-quality contextual translation is not prepared”

Open:

**Settings → Model Manager → Contextual translation · Qwen3 8B · quality → Prepare / verify contextual translation**

DubLocal reuses an existing `llama.cpp` installation when available. Otherwise it can install it through Homebrew, then download/register the pinned Qwen3 8B Q4_K_M model in the shared Hugging Face cache.

## Why is the model about 5 GB?

The v0.4.1 Qwen3 4B development backend proved too weak for the intended quality target in real-language tests. v0.4.2 uses Qwen3 8B Q4_K_M, about 5.03 GB, as the recommended Best-quality model.

If storage or latency matters more than quality, **Fast legacy · OPUS** remains an explicit option. DubLocal does not silently switch engines.

## What happened to the old Qwen3 4B model?

v0.4.2 no longer selects or downloads it. The model remains in `MODEL_LICENSES.json` for provenance only.

If a 4B snapshot was previously downloaded into the shared Hugging Face cache, DubLocal does not automatically delete that shared asset because another local application may be using it.

## Qwen checksum failure

DubLocal pins an immutable upstream revision and SHA-256. If the file hash does not match, it is not registered.

Do not bypass this check. A repeatable mismatch means the registry/upstream state needs review.

## `llama.cpp` missing after preparation

Check **Settings → Local Resources**. `llama-cli` should be visible; modern Homebrew llama.cpp installations commonly also expose `llama-server`.

Restart DubLocal and rescan Local Resources if Homebrew just installed the package.

## Translation takes longer than OPUS

Expected. Best quality uses a much larger generative model, context and normally a second senior-review pass.

DubLocal avoids needless startup overhead by preferring one local loopback `llama-server` session for the whole job. The model is loaded once and reused for translation, recovery and review.

Short media also uses larger chunks, so a short song normally needs far fewer model calls than the old implementation.

## Why does a long movie use more context?

This is intentional. The input context budget grows from roughly 4,096 tokens for short media toward a 24,576-token ceiling.

DubLocal combines:

- nearby source dialogue;
- sampled programme-wide dialogue;
- recent approved translations as rolling terminology/style memory.

The entire movie is not blindly appended to every request.

## `[MUSIC]` became “музыка” / another translated word

That indicates an old build or a regression. In v0.4.2 standalone bracketed cues are structural tags and bypass translation entirely.

`[MUSIC]`, `[APPLAUSE]`, `[LAUGHTER]` and similar standalone cues should remain byte-for-byte unchanged.

## Russian output contains Chinese characters such as `我的心` or `呕`

v0.4.2 rejects that output before writing the translated SRT. CJK/Hangul characters are not valid contamination for the current European translation targets.

If you still see such characters after updating/restarting, report the running version shown at the top of Settings and the exact subtitle line.

## Russian output contains untranslated English words such as “steak” or whole English fragments

v0.4.2 adds target-script validation. A proper name can legitimately remain Latin, but substantial ordinary Latin-script leakage into Russian/Ukrainian is rejected and sent through contextual recovery.

Small isolated errors can still be linguistic rather than structural. Best quality therefore also uses Qwen3 8B plus the senior review pass.

## Translation is grammatical but semantically wrong

First inspect the **Original** column.

If the source subtitle itself is wrong — common with automatic song captions — DubLocal cannot safely infer the real sung/spoken words from translation context alone. Re-transcribe from audio with Accurate Whisper.

If the English/source line is clear and the translation is still wrong, that is a translation-quality defect. Save a small lawful source/translation example when reporting it. The distinction matters because the fix is different.

## Translation sounds too literal or like translated English

Best quality explicitly asks for idiomatic target-language grammar and then reviews the draft a second time for calques, agreement errors, bad word choice and untranslated ordinary words.

For Russian, the quality rules specifically require natural case/gender/number/aspect and prohibit pseudo-Russian transliterations of English words.

## Translation output is missing/duplicated/misaligned

DubLocal uses strict subtitle IDs. The normal pass, recovery pass and single-line recovery all retain the original context.

Every expected ID must be present exactly once before output is written. Timestamps/order are never shifted to accommodate a model mistake.

If alignment still cannot be proved, the job stops instead of writing a corrupt SRT.

## llama.cpp text appears inside a subtitle

Strings such as `Loading model`, `.gguf`, model paths, prompts or runtime banners are never valid subtitle translations. v0.4.2 rejects them before writing output.

The preferred llama-server path also separates generated content from server logs by design. Server logs remain temporary files in DubLocal's job cache.

# Fast legacy OPUS

## Why does OPUS produce literal or strange dialogue?

The legacy engine translates subtitle texts sentence-by-sentence. It remains only as the explicit smaller/faster option.

Use **Best quality · Qwen3 8B + review** for normal quality work.

## OPUS model missing

Use **Settings → Model Manager → Fast legacy translation · OPUS** and install the required direction(s). Non-English ↔ non-English uses two local passes through English.

# Kokoro / M4

## Another app has Kokoro but DubLocal does not detect it

Use **Settings → Local Resources → Rescan local resources** after updating. A reusable environment must expose `kokoro`, NumPy, PyTorch and Hugging Face Hub.

DubLocal invokes that environment's Python as an isolated worker; it does not import another environment's `site-packages` directly.

## Kokoro language unsupported

Official Kokoro coverage exposed by DubLocal includes American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Hungarian, Russian and German can be translation targets but are not official Kokoro voice languages. This is a TTS limitation, not a translation failure.

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

Automatic update/repair will not rewrite local Git history. This requires manual Git review.

## Update installed but UI is old

Click **Restart DubLocal**. If necessary reopen the launcher and choose **Stop All & Launch**.

Check the explicit running version at the top of Settings when reporting a discrepancy.

## Still stuck?

Provide:

- the running version shown in Settings;
- exact text from the nearest DubLocal status box;
- source type (YouTube/local);
- whether the source subtitle was creator/embedded, YouTube automatic, or local Whisper;
- action clicked immediately before the error;
- launcher log tail only for startup/launcher failures.

Do not post account cookies, authentication tokens, copyrighted media you cannot share, or private paths you do not want public.
