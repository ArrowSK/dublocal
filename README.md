<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, translation and AI voice-over tooling for macOS.<br>
  Your media stays on your Mac unless you explicitly use a remote source such as YouTube.
</p>

<p align="center">
  <strong>Current development build: v0.4.0.dev0 · M4 Local Voice</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal is for a simple problem: you have a video or audio file — or a YouTube link you are allowed to process — and you want subtitles, translation and a local synthetic voice track without sending the media through a cloud transcription, translation or TTS service.

M4 now covers source/caption acquisition, local Whisper transcription, local OPUS subtitle translation and local Kokoro voice generation. It deliberately stops before changing the original movie soundtrack; timing fit, ducking/mixing and media remuxing come next.

## Latest development build — v0.4.0.dev0 / M4

M4 adds:

- Kokoro local TTS;
- reuse of an existing compatible Kokoro virtual environment through an isolated worker process;
- fallback installation into DubLocal only when no reusable runtime exists;
- official language/voice selection;
- voice-only WAV generation from source or translated subtitles;
- per-segment WAVs plus a JSON generation manifest;
- exact subtitle-start placement in the generated voice track;
- overflow reporting when synthetic speech is longer than its subtitle window;
- explicit Kokoro preparation under **Settings → Model Manager**;
- a macOS venv-discovery fix so environments such as `~/narroam-studio/.venv/bin/python` are not lost by resolving their Python symlink.

There is currently **no packaged GitHub Release**. `v0.4.0.dev0` is the latest development build on `main` once this milestone is merged. See [CHANGELOG.md](CHANGELOG.md) for the build history.

## What works today

| Stage | Status | What DubLocal does |
| --- | --- | --- |
| Media input | ✅ | YouTube URL or local video/audio |
| Existing subtitles | ✅ | Finds embedded/local and YouTube caption tracks |
| Missing captions | ✅ | Creates timestamped subtitles locally with whisper.cpp |
| Subtitle translation | ✅ | Translates the timed SRT locally with optional OPUS models |
| AI voice | ✅ M4 | Generates a local Kokoro voice-only WAV from an SRT timeline |
| Timing / soundtrack mix | Next | Fit speech into subtitle windows and duck/mix original audio |
| Media export | Planned | Stream-copy compatible video; replace/add dubbed audio track |

## Main vs Settings

DubLocal keeps ordinary processing separate from maintenance.

### Main

Use **Main** for the current job:

1. Choose **YouTube** or **Local file** and scan it.
2. Extract an existing subtitle track or run **Transcribe locally**.
3. Translate the SRT if needed.
4. Open **Local voice · Kokoro**.
5. Choose whether to narrate the translated or source subtitles.
6. Choose a supported Kokoro language/voice and click **Generate voice track**.
7. Listen to/download the voice-only WAV and review which subtitle windows are too short for the generated speech.

M4 keeps the subtitle start times intact. If a generated line is longer than its current subtitle window, DubLocal reports the overrun instead of silently time-stretching or rewriting the text. M5 handles timing adaptation.

### Settings

Use **Settings** for the application itself:

- **Updates** — check/install updates, repair installation, restart.
- **Model Manager** — install/verify/remove Whisper and OPUS models and prepare/verify Kokoro.
- **Local Resources** — inspect FFmpeg, ffprobe, whisper.cpp, Hugging Face cache and reusable external Python runtimes.

To install a translation model:

**Settings → Model Manager → OPUS · subtitle translation → choose model set → Install / verify required model(s)**

To prepare Kokoro:

**Settings → Model Manager → Kokoro · voice generation → choose language/voice → Prepare / verify Kokoro**

DubLocal first looks for a compatible external Kokoro environment. If one exists, it is used through a separate Python worker rather than copied into DubLocal.

## Reuse first, install second

DubLocal deliberately avoids duplicating large local dependencies when safe reuse is possible.

System tools such as **FFmpeg**, **ffprobe** and **whisper.cpp** are used where they are already installed. OPUS and Kokoro model assets use the normal shared Hugging Face cache.

Python virtual environments remain isolation boundaries. DubLocal never imports another application's `site-packages` into its own interpreter. Instead, supported backends run an isolated worker with that environment's own Python executable.

M4 also fixes a subtle macOS issue: venv Python executables are often symlinks to the same framework Python. DubLocal now preserves the venv path itself rather than resolving the symlink and accidentally treating separate environments as one.

## Kokoro language coverage in M4

Official Kokoro support exposed by DubLocal is:

- American English;
- British English;
- Spanish;
- French;
- Hindi;
- Italian;
- Japanese;
- Brazilian Portuguese;
- Mandarin Chinese.

This means a translated subtitle target such as **Hungarian, Russian or German can still be generated as subtitles, but not voiced by official Kokoro**. DubLocal does not silently use the wrong frontend. Additional local TTS backends can fill those language gaps later.

## Install on macOS

The current development installation uses Git so DubLocal can update and repair itself from the official repository.

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

After that, normal use is through **DubLocal.app**, not Terminal.

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for the detailed installation guide.

## Updates and repair

Open **Settings → Updates**.

Normal flow:

**Check for updates → Install update → Restart DubLocal**

Normal updates accept only a clean fast-forward from official `ArrowSK/dublocal` `main` and never overwrite tracked local edits.

**Repair installation** is the explicit recovery path. It can save modified tracked program files as a patch backup, restore official files, refresh/verify the managed Python core and restart cleanly without deleting models, caches, generated jobs or untracked user files.

## Supported M3/M4 translation languages

The current translation UI allowlist is:

English, Hungarian, Russian, German, French, Spanish, Italian, Portuguese, Polish, Ukrainian, Serbian and Croatian.

The translation language list is broader than Kokoro's voice-language list. Translation and TTS are deliberately separate backends.

## Planned dubbed-media output

DubLocal will not re-encode video merely because a dubbed audio stream is being created. Where the source codec/container is compatible, FFmpeg will stream-copy the original video and process only the new audio.

The planned M5 output choice is:

- **Replace primary audio — default:** make the DubLocal mixed soundtrack the default/primary audio stream while keeping music/effects underneath the translated speech.
- **Add dubbed audio as second track:** preserve the original audio unchanged and add the DubLocal mix as another selectable audio stream.

MKV will be preferred for maximum multi-track preservation; MP4 remains available when the selected streams/codecs are compatible.

## Where files live

```text
~/dublocal/                         cloned application source
~/Library/.../DubLocal/models/      DubLocal model registrations / legacy local models
~/.cache/huggingface/hub/           normal shared Hugging Face model cache (default)
~/Library/Caches/.../DubLocal/jobs/ generated SRTs, segment WAVs, voice tracks and manifests
~/.dublocal/logs/                   launcher log
~/.dublocal/repair-backups/         patch backups created by Repair installation
```

Exact platform data/cache locations are resolved using `platformdirs`; `HF_HOME` and `HF_HUB_CACHE` are respected.

## Documentation

- [Changelog](CHANGELOG.md) — current development build and milestone history.
- [User guide](docs/USER_GUIDE.md) — Main, Settings, models and normal day-to-day workflow.
- [Installation](docs/INSTALLATION.md) — launcher, first install, updates and repair.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — practical recovery steps.
- [Architecture](docs/ARCHITECTURE.md) — local pipeline and reusable-backend design.
- [Third-party licences](THIRD_PARTY_LICENSES.md) and [model registry](MODEL_LICENSES.json).

## Roadmap

```text
M1  Source + existing captions                          ✅
M2  Local transcription / Whisper                       ✅ validated
M3  Local subtitle translation + Settings/Model Manager ✅
M4  Kokoro local voice generation                       ✅ implementation
M5  Voice timing + audio mix + stream-copy export       next
M6  Preview + final rendered/remuxed media               planned
M7  Signed/notarized Mac packaging                      planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json` for the current inventory.
