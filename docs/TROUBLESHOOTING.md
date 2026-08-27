# DubLocal troubleshooting

**Applies to v0.5.0.dev0 — M5 Local Dubbed Media Export.**

Most DubLocal failures belong to one stage. Fix that stage rather than reinstalling the entire app or deleting models/caches blindly.

## DubLocal.app opens nothing

Use **Stop DubLocal.app**, reopen **DubLocal.app**, then choose **Stop All & Launch**.

Launcher log:

```text
~/.dublocal/logs/dublocal.log
```

If the managed environment itself is missing, rerun:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

## Generated file shows a Gradio file-access error

Update DubLocal and restart. User-facing generated files must live under DubLocal's own jobs cache, which the local Gradio runtime explicitly allows.

## Where do temporary files go?

Temporary YouTube media, 16 kHz Whisper WAVs, generated subtitles, llama-server logs, TTS segments, fitted voice tracks, dubbed mixes and M5 remux outputs live under:

```text
~/Library/Caches/DubLocal/jobs/
```

On normal launch DubLocal removes job folders older than 24 hours and caps this temporary cache at 4 GiB by removing the oldest jobs first.

Persistent Whisper/Qwen/Kokoro assets and the shared Hugging Face cache are not part of that cleanup.

# Source / YouTube

## YouTube HTTP 429

YouTube is temporarily rate-limiting caption or media delivery. DubLocal retries ordinary retrieval but does not bypass the restriction.

If captions are blocked, use **Transcribe locally**. If YouTube also refuses the audio/media download required for local transcription or M5 export, wait and retry or use a local copy you have the right to process.

## Load source says OK but the wrong old language appears later

v0.5 resets the remembered source-language state when a new source is loaded. Update and restart if an older build appears to reuse the previous job's language.

# Transcription

## FFmpeg / ffprobe / whisper.cpp missing

Check **Settings → Local Resources** first.

The macOS installer can offer Homebrew packages for missing media/transcription tools. Whisper model weights are separate and are managed under **Settings → Model Manager → Whisper**.

## Whisper checksum failure

DubLocal rejects a Whisper model whose checksum does not match the registered upstream hash. Retry the model installation; do not force a partial or unknown file into place.

## Transcription is slow or inaccurate

Base prioritizes practicality. Small is stronger but slower. **Accurate · Large v3 Turbo Q5** is the preferred local quality choice for songs, accents, noisy material or obviously damaged automatic captions.

Apple Silicon normally benefits from whisper.cpp Metal acceleration; Intel uses CPU compatibility mode.

## Auto-detected language did not populate Translate → From

v0.5 normalizes both ISO-style values such as `en` and human labels such as `English`, `Russian` and `Spanish` from Whisper/track metadata.

After a successful transcription the status should show a concrete source language and **Translate → From** should update to that language.

If it still says Auto detect:

1. check the transcription status: if Whisper itself returned no usable language, choose `From` manually;
2. restart after updating to v0.5 so the current UI adapter is loaded;
3. include the exact `[language]` line from activity details when reporting the bug.

DubLocal intentionally does not guess a language from translated text when the upstream detector supplied no usable result.

# Contextual translation — Recommended for this Mac

## Why does my Mac show Lightweight, Balanced or Best quality?

Current conservative profiles are:

```text
Apple Silicon < 12 GB     Qwen3 4B · review off · 8k input cap
Apple Silicon 12–23 GB    Qwen3 8B · review off · 16k input cap
Apple Silicon 24 GB+      Qwen3 8B · review on  · 24k input cap
Intel < 24 GB             Qwen3 4B · review off · smaller context
Intel 24 GB+              Qwen3 8B · review off · reduced context
```

Open **Translation engine details** or **Settings → Model Manager → Contextual translation** to see the exact detected hardware, model, context budget and runtime allocation.

These are recommendations rather than statements that another profile can never run.

## I have an 8 GB M1. Why is Qwen3 4B recommended?

Because model weights are only part of memory use. macOS, the model and llama.cpp's KV/context cache all compete for unified memory.

The lightweight profile also reduces the actual llama.cpp context allocation; it does not reserve a 32k context and merely send a smaller prompt.

## “Contextual translation is not prepared”

Open:

**Settings → Model Manager → Contextual translation → Prepare / verify contextual translation**

DubLocal detects the hardware profile, reuses/installs llama.cpp and downloads only the recommended Qwen model.

Approximate sizes:

- Qwen3 4B Q4_K_M: 2.5 GB;
- Qwen3 8B Q4_K_M: 5.03 GB.

Both are checksum-verified before registration.

## Contextual translation is slower than OPUS

Expected. Qwen3 performs generative translation with context. OPUS remains available when speed/minimum storage is more important than discourse quality.

## Translation contains missing/duplicated/shifted subtitle lines

DubLocal preserves IDs and original timings. Every contextual chunk is validated and malformed/missing IDs go through contextual recovery.

If alignment still cannot be proven, DubLocal stops instead of writing a shifted SRT. Report the exact visible error rather than editing the generated internal cache file.

## Translation contains Chinese characters, untranslated English or runtime text

That output should be rejected before a translated SRT is written for the supported target set.

v0.5 validates for:

- unexpected non-target script contamination;
- substantial wrong-script leakage;
- llama runtime/model/prompt text;
- protected caption cues.

If such content survives into a v0.5 translated SRT, report the smallest reproducible source/translation sample plus running version.

## Translation still gets gender wrong

v0.5 explicitly asks the contextual model and optional review pass to resolve grammatical gender, speaker/addressee relationships, pronouns and recurring entities from surrounding context.

It is still possible for a local model to infer incorrectly when the source is ambiguous. Check whether the surrounding source actually establishes the person's gender/reference. DubLocal deliberately tells the model not to invent unsupported gender simply to make the target language more specific.

If the source clearly establishes it and the result is wrong, keep the shortest source/context example that proves the mismatch; that is useful for prompt/model regression testing.

## Idiom or phraseologism is translated literally

v0.5 explicitly instructs the contextual model to translate idioms and phraseological expressions by meaning, register and conversational function, not word-for-word.

A literal result can still occur with smaller local models. The Best-quality profile's review pass checks this again. Report the smallest example with several neighboring source lines so the intended idiom is visible in context.

## Metaphor sounds wrong

The prompt now distinguishes intentional imagery from literal prose: preserve the metaphor's function/image when it is supported, but do not invent additional imagery.

If the source transcription itself is garbled, fix the source timeline first; translation cannot reliably reconstruct the missing original lyric/dialogue.

# Fast legacy OPUS

## Why does OPUS produce literal dialogue?

The legacy engine translates subtitle text sentence-by-sentence. Keep it for quick/minimum-storage jobs; use **Recommended for this Mac** when context matters.

## OPUS model missing

Use **Settings → Model Manager → Fast legacy translation · OPUS** and install the required direction(s). Non-English ↔ non-English uses two local passes through English.

# Voice-over / Kokoro

## Another app has Kokoro but DubLocal does not detect it

Use **Settings → Local Resources → Rescan local resources**. A reusable environment must expose Kokoro, NumPy, PyTorch and Hugging Face Hub.

DubLocal does not import another application's `site-packages`; it invokes the compatible environment's Python as an isolated worker process.

## Kokoro language unsupported

Official Kokoro frontends exposed by DubLocal currently include American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

A language can be translated even when Kokoro cannot voice it. DubLocal does not silently use the wrong pronunciation frontend.

## Voice-over reads `[MUSIC]`, `[LAUGHTER]` or other bracketed cues

v0.5 removes bracketed caption cues from a **temporary TTS-only timeline** before Kokoro runs. The actual subtitle file is unchanged.

Expected behavior:

```text
[MUSIC]            subtitle kept; nothing spoken
[LAUGHS] Hello     subtitle kept; only “Hello” spoken
```

If Kokoro still speaks a bracketed cue after updating/restarting to v0.5, include the exact subtitle line that triggered it.

## The voice-only preview has long/overlapping lines

The M4 voice preview preserves original start times and shows overflows diagnostically. M5 performs the first timing-fit step during final export.

# M5 dubbed-media export

## What does “Replace primary audio” actually do?

It does not erase all source audio and replace it with dry TTS.

DubLocal takes the source's first audio stream, ducks it while synthesized speech is active, overlays the voice and encodes a new AAC dubbed mix. That new mix becomes the default/primary audio track. Additional original audio tracks are preserved where possible.

This is **ducking + overlay**, not true dialogue/background source separation. Original dialogue can remain quietly audible beneath the dub.

## What does “Add dubbed audio as second track” do?

All original audio tracks are kept untouched and the DubLocal mixed soundtrack is added as another selectable audio track with language/title metadata.

Use MKV when preserving several heterogeneous tracks is important.

## Why is MKV recommended?

MKV can carry a wider mix of existing video/audio/subtitle codecs without transcoding.

MP4 is offered only when the selected streams can be remuxed compatibly. DubLocal will not silently begin a long video transcode just because MP4 was requested.

## MP4 export says to use MKV

The source contains a video/audio/subtitle stream combination that cannot be copied into MP4 as requested.

Choose **MKV · recommended**. This preserves the stream-copy design and avoids generation loss/time from unnecessary video re-encoding.

## Is the video re-encoded?

For compatible local/YouTube source media, M5 maps the original video stream with `-c:v copy`. The video bitstream is therefore copied rather than re-encoded.

The **new dubbed audio** must be processed/encoded because it is a new mix. “No video re-encoding” does not mean “no audio processing”.

## A dubbed line is too long

M5 never intentionally cuts spoken words. It first borrows real silence up to the next spoken line, then uses FFmpeg `atempo` up to 1.25× if needed.

If a line still cannot fit, the final status reports residual timing overflow instead of silently truncating speech.

Future semantic shortening/rephrasing can improve these difficult cases without changing the remux architecture.

## Final dubbed file has original dialogue underneath

Expected with the current M5 design. Sidechain ducking lowers the source soundtrack but does not separate dialogue from music/effects.

True source separation is a separate future feature and is not implied by the current “Replace primary audio” label.

## M5 cannot find `voice-manifest.json`

If the selected voice WAV was produced by the current Kokoro stage, its manifest should be next to it. If a standalone WAV has no manifest, DubLocal can use the already synchronized track but cannot perform per-segment duration fitting from missing segment metadata.

Regenerate the voice track in DubLocal when detailed timing fitting is needed.

# Filenames

## Why is the generated subtitle no longer called `captions.srt`?

Internal cache files can still use generic names, but user-facing v0.5 outputs are copied to readable media-derived filenames:

```text
Movie Name.en.srt
Movie Name.ru.srt
Track Title.es.vtt
```

Translated subtitles use the target-language suffix.

## Why does a filename use `.und.`?

`und` means the language could not be determined reliably. Set the source/target language explicitly if you want a concrete language suffix.

# Updates / repair

## Updater reports modified tracked files

Normal update refuses to overwrite them. Use **Repair installation** only when the edits are accidental or the installation needs recovery. When replacement is authorized, DubLocal saves a patch backup first.

Backups:

```text
~/.dublocal/repair-backups/
```

## Branch is ahead/diverged

Automatic update/repair will not rewrite local Git history. This requires manual Git review.

## Update installed but UI is old

Click **Restart DubLocal**. If necessary reopen the launcher and choose **Stop All & Launch**.

## Still stuck?

Provide:

- exact text from the nearest persistent DubLocal status box;
- running DubLocal version from Settings;
- source type (YouTube/local);
- action clicked immediately before the error;
- detected source language if transcription/translation is involved;
- detected contextual hardware/profile if translation is involved;
- selected M5 mode/container if export is involved;
- launcher log tail only for startup/launcher failures.

Do not post account cookies, authentication tokens, copyrighted media you cannot share, or private paths you do not want public.
