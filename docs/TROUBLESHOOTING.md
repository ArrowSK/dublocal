# DubLocal troubleshooting

This page is for concrete problems. Start with the symptom you actually see; avoid reinstalling everything unless the specific fix says to.

## YouTube says HTTP 429 / Too Many Requests

This means YouTube is temporarily refusing the caption or media request. It is not a DubLocal launcher failure.

What to do:

- If caption extraction fails, try **Transcribe locally** instead.
- If local transcription also reports a YouTube rate limit, YouTube is refusing the audio request too. Wait and retry later, or use a local copy of media you are allowed to process.
- Repeated rapid retries can make rate limiting worse, so do not hammer the same request continuously.

DubLocal does not bypass YouTube access controls or rate limits.

## The updater says local changes were detected

The in-app updater refuses to overwrite a dirty Git checkout.

This is deliberate. It protects developer edits and also catches accidental changes inside the installation folder.

From Terminal, inspect the checkout:

```bash
cd ~/dublocal
git status
```

If the changes are files you intentionally edited, keep them and review/update manually.

If the only changes are known accidental modifications and you are certain they can be discarded, restore only those named files rather than resetting the whole repository blindly. For example:

```bash
git restore path/to/file
```

Then reopen **DubLocal updates** and check again.

Avoid `git reset --hard` as a generic troubleshooting step; it can destroy work.

## The updater says the branch diverged or is ahead of GitHub

That means the checkout contains Git history that is not a simple older copy of the configured upstream.

DubLocal will not decide which commits to keep. Use Git manually or review the checkout with someone who understands the local changes. Automatic update becomes available again once the branch is a clean fast-forward candidate.

## DubLocal.app opens but the page does not load

Check the launcher log:

```text
~/.dublocal/logs/dublocal.log
```

The launcher normally waits for `http://127.0.0.1:7861` to respond before opening the page.

If an old or stuck process exists, reopen **DubLocal.app** and choose **Stop All & Launch**.

## The launcher says the Python environment is missing

The `.venv` inside the DubLocal checkout is missing or incomplete.

Run the installer again:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

The installer can create the environment again without deleting Whisper models stored outside the repository.

## Python 3.11+ is missing

The installer can offer to install Python 3.11 through Homebrew when Homebrew is available.

If Homebrew is not available, install Python 3.11 or newer through a normal macOS Python distribution and rerun the installer.

## FFmpeg or ffprobe is missing

Local media inspection, subtitle extraction and transcription audio preparation need FFmpeg.

Rerun:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

If Homebrew is available, the installer offers `brew install ffmpeg`.

YouTube metadata/caption discovery may still work without FFmpeg, but local media and local transcription will not be complete.

## whisper.cpp / whisper-cli is missing

Local transcription needs the `whisper-cli` executable.

Rerun the installer and allow the optional whisper.cpp engine installation when prompted:

```bash
cd ~/dublocal
zsh scripts/macos/install-launcher.sh
```

Existing-caption extraction does not require whisper.cpp.

## A Whisper model is not installed

Open **Local transcription · Whisper**, choose Tiny/Base/Small and click **Install / verify model**.

The app intentionally does not download a model automatically.

## A Whisper model fails checksum verification

DubLocal deletes the failed download rather than using it.

Try the install again. If it repeatedly fails, do not manually rename or force the partial file into place; the upstream file or download path may need investigation.

## Transcription is slow

Transcription speed depends on model size, audio duration and Mac hardware.

Try **Base** before **Small**. For a quick functional test, use **Tiny**.

Apple Silicon follows whisper.cpp's Metal path. Intel Macs use the CPU path, so longer files can take noticeably more time.

## Local subtitles are listed but cannot be extracted

The track may be image-based (for example, PGS). M2 does not OCR image subtitle streams.

Use local speech transcription if that is appropriate for the content. OCR support is a separate future capability.

## The subtitle output looks empty or incomplete

First determine which path produced it:

- existing subtitle extraction: try another listed subtitle track if one exists;
- Whisper transcription: try a larger model or set the spoken language manually instead of Auto.

If the source audio itself is quiet, noisy, mixed with music or contains overlapping speakers, transcription quality can degrade.

## Git pull says local changes would be overwritten

That is the command-line version of the updater safety block.

Run:

```bash
cd ~/dublocal
git status
```

Review exactly which files changed. Restore only files you know are accidental, then pull again.

## macOS Terminal shows an unrelated .zprofile error

A shell startup message such as:

```text
~/.zprofile:... command not found
```

comes from the user's shell configuration, not from DubLocal itself. It should be fixed separately if it is annoying, but it is only a DubLocal blocker if it prevents normal commands such as `git`, `python`, `brew`, or `zsh` from running.

## Where to report a reproducible bug

When opening a GitHub issue, include:

- what you clicked;
- whether the source was YouTube or local media;
- the exact error shown inside DubLocal;
- macOS version and Apple Silicon/Intel;
- the relevant tail of `~/.dublocal/logs/dublocal.log` if the launcher failed.

Do not upload copyrighted media, private URLs, authentication cookies, or other sensitive data just to demonstrate a bug.
