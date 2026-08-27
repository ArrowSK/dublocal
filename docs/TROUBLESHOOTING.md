# DubLocal troubleshooting

**Applies to v0.5.3.dev0 — M5 Stabilization.**

Most failures belong to one stage. Fix that stage rather than deleting models/caches or reinstalling everything.

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

Normal launch removes jobs older than 24 hours and caps the cache at 4 GiB. Persistent AI models/shared Hugging Face assets are not deleted.

# Source / YouTube

## HTTP 429

YouTube is temporarily rate-limiting caption/media delivery. DubLocal retries normal retrieval but does not bypass the restriction.

If captions are blocked, use local transcription. If media delivery is also blocked, wait/retry or use a local copy you have the right to process.

# Transcription

## Native tools missing

Check **Settings → Local Resources**. The installer/repair flow can restore FFmpeg/ffprobe/whisper.cpp integration. Whisper weights are managed separately under Model Manager.

## Whisper invented speech or repeats one phrase

Do not translate/dub a hallucinated SRT.

v0.5.3 keeps several protections:

- supported ordinary-speech paths may use Silero VAD;
- Accurate music transcription disables rolling text context that can self-seed repetition;
- long near-duplicate storms are isolated and retried;
- a severe persistent storm is suppressed rather than trusted.

For songs/difficult vocals prefer **Accurate · Large v3 Turbo Q5**.

If a severe loop survives after v0.5.3, provide the affected SRT time range. The raw decoder output is temporary diagnostic data; the cleaned result is what downstream stages receive.

## Some real words were missed

v0.5.3 does **not** globally lower Whisper thresholds because that would reintroduce ghost speech.

Instead, it selectively examines suspicious sparse lines and, for Accurate music mode, short internal holes. A candidate is accepted only if two isolated no-context decoding passes agree closely and the text does not simply echo a neighbouring subtitle.

On Apple Silicon below 12 GiB this extra analysis is capped at 3 regions / 24 seconds.

A remaining gap is preferable to invented dialogue. If a specific word is still missing, keep the shortest time range around that omission for a regression example.

## Auto language / Translate From=Auto

After local Auto transcription, the status should normally contain a concrete detected language. Contextual translation also supports **From = Auto** directly: when no reliable language state exists, the already-loaded local Qwen runtime identifies the dominant subtitle language before translating.

If Auto still cannot determine a supported language, select From manually and report the exact status message.

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

If the English/source text is correct, preserve the shortest failing example with nearby context. The prompt/review explicitly handles discourse reference/gender where supported, idioms/phraseology by meaning/register and metaphor fidelity.

## Wrong-script characters, prompt/runtime text or shifted IDs

Those should be rejected before a translated SRT is written. If any survive, report the smallest source/translation sample plus the running version.

# Voice-over

## Kokoro exists elsewhere but is not detected

Use **Settings → Local Resources → Rescan**. DubLocal reuses a compatible external Kokoro environment through a separate process; it never injects another environment into its interpreter.

## It reads `[MUSIC]`

It should not. Tag-only cues produce no speech and inline cues are removed only from the temporary TTS input:

```text
[MUSIC]            subtitle kept; silence
[LAUGHS] Hello     subtitle kept; speaks “Hello”
```

## Auto voice picked the wrong range

Auto voice matching is a lightweight F0/range heuristic, not diarization. Music/noise, overlap and weak pitch evidence can make it fall back or choose imperfectly. Use a manual Kokoro voice for deterministic casting.

It does not load two TTS models; one pipeline remains loaded while presets change.

# Export

## The soundtrack becomes much louder between dubbed lines

This was a specific pre-v0.5.3 failure. v0.5.3 keeps the original programme at a stable reduced bed level and attenuates it further during source dialogue/singing windows. Gentle compression/limiting controls the final mix.

If the level still pumps strongly, report a short time range plus whether source subtitle windows cover that region. DubLocal is still working from a married mix, not a dialogue-free M&E stem.

## Original dialogue/singing remains audible

DubLocal suppresses the original mix across the full source subtitle window, but it cannot perfectly remove a vocal from a married soundtrack without source separation. This remains ducking/attenuation + overlay by design.

## Dub finishes too early or too late

v0.5.3 measures every generated WAV against its subtitle window and can chain FFmpeg `atempo` stages for an effective 0.30×–2.50× range. A small correction pass handles rounding if the end is still more than roughly 25 ms off.

Subtitle timestamps are not moved. If a line would need an even more extreme stretch, DubLocal reports it rather than forcing unusable audio.

When reporting timing, provide one subtitle start/end and the corresponding translated text. That is more useful than shifting the whole SRT.

## I only want the original media with subtitles

Choose:

**Package original + subtitles · no dub**

This keeps original audio, embeds only the current source/transcribed subtitle, and adds neither translated subtitles nor a DubLocal audio track.

## Both subtitles are not visible in VLC

Normal dubbed export embeds generated source + translated subtitles when both exist. MKV presents them as selectable streams; MP4 converts generated SRT to `mov_text` when compatible.

The subtitle-only export intentionally embeds only the source/transcribed subtitle.

## Is video re-encoded?

### Local

**Original / best available** uses video stream-copy. Selecting a lower resolution explicitly enables H.264 VideoToolbox encoding. DubLocal does not upscale a lower-resolution source.

### YouTube

The selected resolution is a maximum source height. yt-dlp acquires an appropriate source, then the final remux stream-copies the video.

## MP4 says to use MKV

The requested stream combination is not safely packageable in MP4 without a hidden transcode. Choose **MKV · recommended**.

# Updates / repair

## Modified tracked files

Normal update refuses to overwrite them. **Repair installation** can save a patch under:

```text
~/.dublocal/repair-backups/
```

then restore official tracked files while preserving models/caches/jobs.

## Update installed but UI is old

Use **Restart DubLocal** or relaunch and choose **Stop All & Launch**.

# Still stuck?

Provide:

- nearest persistent status message;
- running version from Settings;
- source type;
- action clicked;
- relevant time range;
- transcription model/language when ASR is involved;
- translation From/To when translation is involved;
- voice mode/language for TTS;
- export mode/container/video quality for remux/mixing issues.

Do not post account cookies, authentication tokens or private media you cannot share.
