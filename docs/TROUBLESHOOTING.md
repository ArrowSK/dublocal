# DubLocal troubleshooting

**Applies to v0.6.0.dev0 — Magic Flow UX.**

Most failures belong to one stage. Fix that stage rather than deleting models/caches or reinstalling everything.

# Launcher / installation

## DubLocal.app opens nothing

Use **Stop DubLocal.app**, reopen **DubLocal.app**, then choose **Stop All & Launch**.

Launcher log:

```text
~/.dublocal/logs/dublocal.log
```

If the managed environment is missing:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

## Temporary files

Working data lives under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes stale jobs and caps temporary job data. Persistent AI models/shared Hugging Face assets are not deleted by job cleanup.

# Magic Flow

## Magic Flow says no subtitle route is ready

Magic Flow never silently downloads a large model.

If no creator/embedded track, suitable automatic caption or installed Whisper model is available, open:

**Settings → Model Manager → Whisper**

Install **Base** for normal use or **Accurate · Large v3 Turbo Q5** for songs/accents/difficult audio, then run Magic Flow again.

## Magic Flow chose a route I do not want

Open **More options → Subtitle source** and choose:

- Prefer an existing subtitle track; or
- Force local transcription.

For complete manual control, use the Detailed workflow below Magic Flow.

## I only want subtitles

In Magic Flow leave **Subtitles** checked and uncheck Translate, Voice-over and Output media file.

The detailed Subtitles stage also remains available and produces standalone SRT/VTT/TXT.

## I want translated subtitles inside the movie but no dub audio

Select:

- Subtitles
- Translate
- Output media file

and leave Voice-over unchecked.

Magic Flow packages the original audio with selectable source/translated subtitle tracks. Nothing is burned into the picture.

## I want the original audio kept too

Leave **More options → Keep original audio as a separate selectable track** checked. MKV is the recommended container for this kind of multi-track output.

## Voice-over is unavailable for the selected language

Translation and subtitles can support languages that the current Kokoro backend cannot speak.

Magic Flow will stop the voice stage with a clear message. Either:

- choose a Kokoro-supported output language;
- uncheck Voice-over/Output media and keep the subtitles/translation; or
- use the Detailed workflow when another TTS backend becomes available.

# Source / YouTube

## HTTP 429

YouTube is temporarily rate-limiting caption/media delivery. DubLocal retries normal retrieval but does not bypass the restriction.

If captions are blocked, use local transcription. If media delivery is also blocked, wait/retry or use a local copy you have the right to process.

# Transcription

## Native tools missing

Check **Settings → Local Resources**. The installer/repair flow can restore FFmpeg/ffprobe/whisper.cpp integration. Whisper weights are managed separately under Model Manager.

## Whisper invented speech or repeats one phrase

Do not translate/dub a hallucinated SRT.

Current protections include:

- supported ordinary-speech paths may use Silero VAD;
- Accurate music transcription disables rolling text context that can self-seed repetition;
- long near-duplicate storms are isolated and retried;
- a severe persistent storm is suppressed rather than trusted.

For songs/difficult vocals prefer **Accurate · Large v3 Turbo Q5**.

If a severe loop survives, preserve the affected SRT time range. Raw decoder output remains temporary diagnostic data; the cleaned result is what downstream stages receive.

## Some real words were missed

DubLocal does **not** globally lower Whisper thresholds because that would reintroduce ghost speech.

Instead, it selectively examines suspicious sparse lines and short internal holes. A candidate is accepted only if two isolated no-context decoding passes agree closely and the text does not simply echo a neighbouring subtitle.

Low-memory Apple Silicon has stricter limits on this extra analysis. A remaining gap is preferable to invented dialogue.

# Auto language / translation

## Transcribe locally detected a language but Translate still says Auto

That is normal UI state: **From = Auto** means “consume the detected language automatically.”

The translation engine should resolve it as follows:

1. use the concrete language detected by local transcription when available;
2. otherwise, for Contextual quality, identify the dominant subtitle language with the already-loaded local Qwen runtime;
3. proceed with translation using the resolved language.

It should not tell you to “choose Auto” when Auto is already selected.

## Auto still cannot identify the source language

Use the Detailed workflow and choose **From** manually. Preserve the translation status/error plus a short SRT sample when reporting the failure.

## Legacy OPUS asks for a manual source language

Expected. OPUS has no contextual language-identification pass. Use Contextual quality for a true `From = Auto` workflow.

# Translation

## Why Lightweight / Balanced / Best quality?

DubLocal scales Qwen and llama.cpp context to hardware:

```text
Apple Silicon <12 GB      Qwen3 4B · 8k
Apple Silicon 12–23 GB    Qwen3 8B · 16k
Apple Silicon 24 GB+      Qwen3 8B + review · up to 24k
Intel <24 GB              Qwen3 4B · smaller context
Intel 24 GB+              Qwen3 8B · reduced context
```

This protects unified memory on M1-class Macs.

## Gender, idiom or metaphor is wrong

First verify the source transcript. Contextual translation cannot recover evidence that ASR removed.

If the source text is correct, preserve the shortest failing example plus nearby context. The prompt/review explicitly handles discourse reference/gender where supported, idioms/phraseology by meaning/register and metaphor fidelity.

# Voice-over

## Voice reads `[MUSIC]` or another bracketed cue

That is a bug. The SRT should preserve the cue, but the temporary speech timeline must remove standalone/non-dialogue bracket cues before Kokoro.

## Auto voice seems wrong

Automatic matching is based on acoustic lower/higher vocal range, not speaker identity. Switch to a manual voice in the Detailed workflow for a particular title if preferred.

# Timing

## Dub ends too early or too late

DubLocal measures each generated segment and targets its subtitle window. Current timing can chain FFmpeg `atempo` stages over an effective 0.30×–2.50× range.

A line requiring more extreme manipulation may remain imperfect rather than being stretched into obviously damaged speech. Preserve the exact subtitle start/end, text and voice-segment duration for a useful report.

# Soundtrack / loudness

## Original soundtrack becomes much louder between dub lines

Current builds keep the original soundtrack at a stable reduced bed and attenuate it further during source dialogue/singing windows. Large jumps should not be normal.

Remember that DubLocal is working from a married soundtrack, not a professional dialogue-free M&E stem. It uses attenuation/compression, not true source separation.

# Export

## I do not want video re-encoding

Choose **Original / best available**.

For local media, this uses video stream-copy. Audio/subtitle changes alone do not imply video recoding.

## MP4 failed but MKV works

Expected for some codec/track combinations. MKV is the recommended multi-track container because it accepts a wider range of source streams without transcoding.

## I want subtitles selectable in VLC, not burned in

Use normal export/Magic Flow media output. Generated subtitles are muxed as tracks rather than burned into the picture.

# Updates / repair

## DubLocal says it is up to date but I expected another build

The updater compares Git revisions. Run **Check for updates** again after the relevant change has been merged to official `main`.

## Local changes block an update

Use **Settings → Updates → Repair installation**. The repair flow is the supported way to reconcile local checkout drift without manually resetting unrelated work.
