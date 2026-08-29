# DubLocal troubleshooting

**Applies to v0.6.0b1 — first packaged macOS beta.**

Most failures belong to one stage. Fix that stage rather than deleting models/caches or reinstalling everything.

# Beta installer / launcher

## macOS says DubLocal cannot be opened because it is from an unidentified developer

0.6.0b1 is intentionally unsigned and not notarized.

Use the normal macOS exception path for this app only:

1. Control-click/right-click **DubLocal.app** and choose **Open**.
2. If macOS still blocks it, open **System Settings → Privacy & Security** and choose **Open Anyway** for DubLocal.

Do not disable Gatekeeper globally.

## First launch appears to do nothing

The first packaged launch may be preparing the managed Git checkout and private Python environment. Check:

```text
~/.dublocal/logs/bootstrap.log
~/.dublocal/logs/dublocal.log
```

The packaged beta keeps its managed source checkout at:

```text
~/Library/Application Support/DubLocal/app
```

If the bootstrap reports missing Git or Python, install/finish the requested component and reopen DubLocal. When Homebrew is already available, the beta can offer to install missing Git/Python and FFmpeg components.

## DubLocal.app opens nothing after setup

If a backend is already running but stuck, the managed launcher can stop/restart it. For a packaged beta checkout:

```bash
cd "$HOME/Library/Application Support/DubLocal/app"
zsh scripts/macos/launch-dublocal.sh
```

Choose **Stop All & Launch** if prompted.

Source/development installations may still use their original checkout and `~/Applications` launchers.

## FFmpeg is missing after first launch

The app can open without FFmpeg, but normal media processing requires FFmpeg/ffprobe. Check **Settings → Local Resources**. If Homebrew is available, install FFmpeg and reopen DubLocal.

## I replaced DubLocal.app but my models/data are still present

Expected. The `/Applications/DubLocal.app` bundle is only the packaged launcher/bootstrap. Models, managed checkout, caches, authenticated sessions and finished outputs live separately. See `BETA_INSTALLATION.md` before deleting application-support/cache/data folders.

# Temporary files / storage

Working data lives under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes stale jobs and caps temporary job data. Settings → **Storage & Cleanup** reports temporary jobs, translation cache, models, runtimes, browser data, logs, resume data and finished outputs.

**Clean temporary files** cannot delete installed models, authenticated website sessions or finished user outputs. If that action refuses to run, stop the active DubLocal job first.

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

For complete manual control, use **Main → Advanced**.

## I only want subtitles

In Magic Flow leave **Subtitles** checked and uncheck Translate, Voice-over and Media file.

The Advanced Subtitles stage also remains available and produces standalone SRT/VTT/TXT.

## I want translated subtitles inside the movie but no dub audio

Select Subtitles, Translate and Media file, leaving Voice-over unchecked.

Magic Flow packages the original audio with selectable source/translated subtitle tracks. Subtitle burn-in happens only for an explicit compatible shareable output choice.

## I want the original audio kept too

Leave **More options → Keep original audio as a separate selectable track** checked. MKV is the recommended container for this kind of multi-track output.

## Voice-over is unavailable for the selected language

Translation and subtitles can support languages that the selected TTS provider cannot speak.

Magic Flow will stop the voice stage with a clear message. Either choose a supported output language/provider, or keep the subtitles/translation without voice-over.

# Course / authenticated website

## Course / Website asks me to sign in again

Use **Open / Sign in** and authenticate in the dedicated DubLocal browser. DubLocal does not ask for the password itself. Close the dedicated browser when finished, then inspect the course again.

If the stored session is bad, clear it under **Settings → Authenticated Websites** and sign in again.

## DubLocal says the source is DRM protected

That is a hard boundary. DubLocal does not extract DRM keys or bypass Widevine/FairPlay/PlayReady protections. Use an official legitimate local download/copy if the platform provides one and you have the right to process it.

## One course lesson failed

The queue is failure-isolated. Successful lessons remain saved and later runs resume completed lessons rather than processing them again. Retry the pending/failed lesson after addressing the acquisition/transcription error.

# Source / YouTube

## HTTP 429

YouTube is temporarily rate-limiting caption/media delivery. DubLocal retries normal retrieval but does not bypass the restriction.

If captions are blocked, use local transcription. If media delivery is also blocked, wait/retry or use a local copy you have the right to process.

# Transcription

## Native tools missing

Check **Settings → Local Resources**. FFmpeg/ffprobe/whisper.cpp are native resources; Whisper weights are managed separately under Model Manager.

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

## Auto still cannot identify the source language

Use Advanced and choose **From** manually. Preserve the translation status/error plus a short SRT sample when reporting the failure.

## Legacy OPUS asks for a manual source language

Expected. OPUS has no contextual language-identification pass. Use Contextual quality for a true `From = Auto` workflow.

# Translation

## Why does Recommended for this Mac choose a smaller model?

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

That is a bug. The SRT should preserve the cue, but the temporary speech timeline must remove standalone/non-dialogue bracket cues before TTS.

## Auto voice seems wrong

Automatic matching is based on acoustic lower/higher vocal range, not speaker identity. Switch to a manual compatible voice in Advanced for a particular title if preferred.

# Timing

## Dub ends too early or too late

DubLocal measures generated segments against subtitle windows and uses native provider timing plus bounded correction where appropriate. A line requiring extreme manipulation may remain imperfect rather than being stretched into obviously damaged speech. Preserve the exact subtitle start/end, text and voice-segment duration for a useful report.

# Soundtrack / loudness

## Original soundtrack becomes much louder between dub lines

Current builds keep the original soundtrack at a stable reduced bed and attenuate it further during source dialogue/singing windows. Large jumps should not be normal.

The lightweight path is attenuation/compression rather than true source separation. Optional local Demucs separation is a separate enhancement for music-heavy material.

# Export

## I do not want video re-encoding

Choose **Original / best available**.

For local/acquired media, this uses video stream-copy where the selected stream/container combination permits it. Audio/subtitle changes alone do not imply video recoding.

## MP4 failed but MKV works

Expected for some codec/track combinations. MKV is the recommended multi-track container because it accepts a wider range of source streams without transcoding.

## I want subtitles selectable in VLC, not burned in

Use normal export/Magic Flow media output. Generated subtitles are muxed as tracks. Burn-in is an explicit shareable-output choice.

# Updates / repair

## Update installs but DubLocal does not reopen

0.6.0b1 uses the hardened detached restart path. If automatic restart fails, reopen **DubLocal.app**; the managed checkout should already contain the updated code. The launcher/backend log is `~/.dublocal/logs/dublocal.log`.

## DubLocal says it is up to date but I expected another build

The updater compares Git revisions. Use **Settings → Updates → Update DubLocal** after the relevant change has been merged to official `main`.

## Local changes block an update

The normal Update action can repair managed tracked-file drift only with backup semantics. It will not overwrite local commits, divergent history, a different branch, or an unexpected upstream. Those cases require deliberate Git review rather than a forced reset.
