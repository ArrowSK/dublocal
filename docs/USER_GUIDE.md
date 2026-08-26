# DubLocal user guide

DubLocal is designed around one simple idea: **use the easiest reliable subtitle source first, and only do heavier local transcription when it is actually needed.**

You do not need to understand FFmpeg, whisper.cpp or subtitle formats to use the normal workflow.

## 1. Open DubLocal

Launch:

```text
~/Applications/DubLocal.app
```

The launcher opens the local DubLocal interface in your default browser. The page is served only from your Mac on `127.0.0.1`.

If DubLocal is already running, the launcher simply opens it. If you have just updated the code, the launcher can start a clean instance.

## 2. Choose the source

### YouTube

Select **YouTube**, paste one video URL, and click **Scan source**.

DubLocal reads the video metadata and lists the subtitle/caption tracks YouTube reports for that video. It does not download the full video merely to perform this scan.

### Local file

Select **Local file**, choose the video or audio file, and click **Scan source**.

DubLocal uses `ffprobe` to inspect the streams and reports the embedded subtitle tracks it can see.

Common media containers such as MKV, MP4, AVI and audio files are the intended input path. Support is ultimately determined by the local FFmpeg build.

## 3. Prefer existing subtitles when they are usable

If the source already has a usable text subtitle/caption track:

1. Select the track.
2. Confirm that you have the right or legal authority to process the media.
3. Click **Extract existing subtitles**.

For local media, text subtitles can be converted to SRT through FFmpeg. Image-based subtitle streams are not silently OCRed; DubLocal tells you that they are not directly extractable by the current milestone.

For YouTube, DubLocal first tries the caption source reported during the scan. If YouTube temporarily refuses caption delivery, DubLocal reports that clearly instead of pretending the track was missing.

## 4. Use local transcription when captions are missing or blocked

Expand **Local transcription · Whisper**.

If no model is installed yet, choose one:

| Model | Size | Recommendation |
| --- | ---: | --- |
| Tiny | 75 MiB | Fastest, useful for testing |
| Base | 142 MiB | Best first choice for normal use |
| Small | 466 MiB | Better accuracy, more time and storage |

Click **Install / verify model**. The download is explicit; DubLocal does not install model weights behind your back.

Then choose the spoken language. **Auto detect** is the normal default. A manual language can help when you already know the source language and want to remove ambiguity.

Click **Transcribe locally**.

DubLocal will:

1. obtain the audio source;
2. convert it locally to 16 kHz mono PCM for whisper.cpp;
3. run the selected Whisper model locally;
4. produce an SRT file with timestamps;
5. show the timed subtitle rows in the UI.

On Apple Silicon, whisper.cpp can use its normal Metal acceleration. Intel Macs use the CPU compatibility path.

## What happens with YouTube HTTP 429?

YouTube can rate-limit caption delivery. When that happens, DubLocal does not endlessly retry or crash.

If the caption request is refused, use **Transcribe locally**. DubLocal then tries to obtain only the media audio needed for local transcription.

There is one important limitation: YouTube can rate-limit media delivery too. If YouTube refuses the audio as well, local transcription cannot magically bypass that restriction. Wait and retry later, or use a local copy of media you are allowed to process.

## 5. Read the subtitle result

The output section gives you:

- the generated/extracted subtitle file;
- a timed table with **Start**, **End** and **Text**;
- a concise status console explaining what happened.

The current internal timeline uses integer milliseconds. That becomes the stable source for the upcoming translation and dubbing layers, so the same media should not need to be retranscribed just because a later translation changes.

## 6. Manage model storage

The Whisper models are optional and live outside the Git repository.

Use **Remove model** if you want the disk space back. Removing a model does not affect existing SRT files or the DubLocal installation.

DubLocal remains useful for existing-caption extraction even with no Whisper model installed.

## 7. Update DubLocal from the app

Expand **DubLocal updates**.

Use:

1. **Check for updates**
2. **Install update** if one is available
3. **Restart DubLocal**

The updater only accepts a clean fast-forward from the configured GitHub upstream. If it detects edits or unusual Git history, it stops and explains why rather than overwriting anything.

This update check is user-initiated; DubLocal does not continuously poll GitHub in the background.

## What DubLocal does not do yet

The current milestone stops at a reliable timed source transcript/subtitle.

Translation, Kokoro voice generation, speech-duration fitting, original-audio ducking and rendered dubbed video are planned next. They will be added on top of the same timestamped timeline rather than replacing the working subtitle/transcription path.

## Practical model choice

Start with **Base**. It is small enough to be convenient and accurate enough to tell whether the workflow suits the material.

Use **Tiny** when speed matters more than accuracy or you are simply testing that everything works. Move to **Small** for more difficult audio when the Base result is not good enough.

## Need help?

Use [Troubleshooting](TROUBLESHOOTING.md) for concrete errors and [Installation](INSTALLATION.md) for setup/update details. Technical implementation notes are kept separately in [Architecture](ARCHITECTURE.md) so the normal user guide stays readable.
