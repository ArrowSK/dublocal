# Install DubLocal 0.6.0b8 on macOS

DubLocal 0.6.0b8 is the current packaged macOS beta. Installation is the familiar Mac pattern: download a DMG, drag the app to Applications, open it.

The only unusual part is the first-launch security prompt. This beta is intentionally **unsigned and not notarized**, so macOS will ask you to approve it once.

## Download

**[Download DubLocal 0.6.0b8 for macOS](https://github.com/ArrowSK/dublocal/releases/download/v0.6.0b8/DubLocal-0.6.0b8-macOS-unsigned.dmg)**

Release page: [v0.6.0b8](https://github.com/ArrowSK/dublocal/releases/tag/v0.6.0b8)

A SHA-256 checksum is published beside the DMG on the release page.

## Install in five steps

1. Open `DubLocal-0.6.0b8-macOS-unsigned.dmg`.
2. Drag **DubLocal.app** onto **Applications**.
3. Open Applications, Control-click/right-click **DubLocal.app**, and choose **Open**.
4. Confirm that you want to open it. If macOS still blocks the app, go to **System Settings → Privacy & Security → Open Anyway**.
5. Let the first-run setup finish. DubLocal will open in your browser when it is ready.

Do **not** disable Gatekeeper globally. The per-app approval above is enough.

## Why macOS shows the warning

The beta does not yet have an Apple Developer ID signature or notarization ticket. That is a distribution limitation, not a request to weaken Mac security.

The package build explicitly verifies that the app is actually unsigned, so the repository and release notes do not claim a security state that the package does not have.

## What is inside the DMG

The DMG is intentionally small. It contains:

- `DubLocal.app` with the DubLocal icon;
- an Applications shortcut for drag-and-drop installation;
- first-launch instructions;
- DubLocal and third-party licence notices.

It does **not** bundle large Whisper, translation, TTS or Demucs model files. Those remain optional and are managed from inside DubLocal.

## What happens the first time you open it

The `.app` is the Mac-facing launcher. On first launch it prepares the managed DubLocal installation here:

```text
~/Library/Application Support/DubLocal/app
```

That folder is an official Git checkout of `ArrowSK/dublocal` on `main`. The first installation is pinned to the exact revision used to build the DMG.

DubLocal also creates a private Python virtual environment inside the managed checkout and installs the core application dependencies there. First setup therefore needs an internet connection and may take a few minutes.

If an older development copy of DubLocal is already running, fresh packaged setup performs a clean takeover/restart so the browser does not quietly remain connected to the older backend.

## What needs to be present on the Mac

### Git

DubLocal uses Git for the managed installation and safe in-app updates. If Git is missing, the app can ask macOS to start the Command Line Tools installation. When Homebrew is already present, it can offer to install Git through Homebrew instead.

### Python 3.11–3.13

The current beta creates its private environment from a compatible local Python. When Homebrew is available, DubLocal can offer to install Python 3.11 if no compatible interpreter is found.

A later fully bundled runtime can remove this beta dependency; 0.6.0b8 does not pretend it is bundled when it is not.

### FFmpeg

FFmpeg/ffprobe are required for normal audio/video processing. DubLocal can still open without them so the missing resource is visible in **Settings → Local Resources**.

There is one extra requirement for **Burn subtitles into Shareable MP4**: the FFmpeg binary doing that export must contain the `subtitles` filter backed by libass. If normal FFmpeg does not provide it, packaged setup/update can offer the side-by-side Homebrew `ffmpeg-full` build without replacing the normal FFmpeg used by the rest of the pipeline.

## Production architecture in beta 8

Beta 8 consolidates the active application around one explicit launcher/UI composition and ordinary service calls. Standard, Advanced, transcription, translation, voice, course import, audio mixing and export no longer depend on import-time function/class replacement or Gradio constructor replacement in the running product path.

Authenticated website safety is also part of the canonical source provider now. Signed HLS/DASH URLs are still checked for encryption/DRM, reusable credential/signing query values are redacted before errors or resume information are persisted, non-secret lesson-routing parameters are preserved, and clearing every lesson selection cannot silently expand back to all lessons.

These are internal reliability changes; the normal user workflow remains **Main → Standard**.

## Hungarian voice-over

Hungarian remains available as an output language for translation and voice-over.

On macOS, **Auto** prefers an installed Hungarian (`hu_HU`) system voice. Piper voices remain available as explicit alternatives. If no Hungarian system voice is installed, Piper is the fallback.

On Windows and other platforms, the Hungarian provider is Piper only. The backend carries Windows CI portability coverage, but DubLocal does **not** publish a Windows installer yet.

The initial Piper voices are **Anna**, **Berta** and **Imre**. Piper is prepared only when requested from Model Manager. Preparation creates a dedicated DubLocal TTS runtime and downloads/verifies the selected voice files. A normal processing job never silently installs the runtime or downloads the voice model halfway through the job.

The Piper runtime is isolated and invoked out of process. The voice model/data and runtime retain their own upstream licences; see [TTS providers](TTS_PROVIDERS.md) and the third-party licence inventory.

macOS system voices are OS-provided resources. DubLocal does not redistribute them and does not assert separate commercial or redistribution rights for generated system-voice output; applicable platform/vendor terms remain relevant.

## Output profiles

DubLocal has persistent **Settings → Output profiles**. MKV, MP4 and Shareable MP4 each have their own **Auto / Original / High / Balanced / Compact** setting.

The default Auto behavior is format-aware:

- **MKV:** preserve source video whenever practical;
- **MP4:** Balanced compatible output, up to 1080p;
- **Shareable MP4:** Compact output, up to 720p.

The Standard workflow stays compact. If you open **Options**, **Resolution limit** can still impose a lower maximum resolution for one job. Compression itself comes from the saved per-format profile.

## Translation performance

The current contextual path keeps the hardware-selected Qwen model and translation-quality rules while reducing repeated prompt/KV work on fragmented captions. Strict subtitle-ID validation and adaptive half-size fallback remain in charge of safety.

No extra setup or quality toggle is required for these optimizations.

## Models and voice engines are opt-in

DubLocal does not silently install multi-gigabyte AI models during setup.

Open **Settings → Model Manager** when you want to add a Whisper or translation model or prepare an optional local voice engine. This keeps the first install small and lets the user decide which local capabilities are worth the disk space.

## Updating DubLocal

Use:

**Settings → Updates → Update DubLocal**

The updater only manages the expected official `main` checkout. It refuses to rewrite an unexpected remote, a divergent history or local commits it cannot safely preserve.

For the packaged beta, an update re-enters the app bootstrap before restart. That lets the private Python environment absorb dependency changes before the new backend starts. The restart is automatic when an update requires one.

## Where your files live

Replacing `DubLocal.app` does not erase models or finished work.

The app bundle, managed program checkout, models, caches, browser sessions and finished outputs are deliberately separate things.

Use **Settings → Storage & Cleanup** to see the major categories. **Clean temporary files** is restricted so it cannot delete installed models, authenticated website sessions or finished user outputs.

## Uninstall

### Remove only the app

Quit DubLocal and move this to Trash:

```text
/Applications/DubLocal.app
```

Your managed installation, models and outputs stay in place.

### Remove the managed program installation too

Also remove:

```text
~/Library/Application Support/DubLocal/app
```

Do not delete the whole DubLocal support/cache/data area unless you intentionally want to remove the remaining model/setup state as well.

## If first launch does not work

Start with [Troubleshooting](TROUBLESHOOTING.md). The useful logs are:

```text
~/.dublocal/logs/bootstrap.log
~/.dublocal/logs/dublocal.log
```

The troubleshooting guide is organized by the stage that failed, so you generally do not need to wipe the installation and start over.
