# DubLocal 0.6.0b1 — first macOS beta package

DubLocal 0.6.0b1 is the first packaged macOS beta. It is distributed as a normal drag-to-Applications DMG and is intentionally **unsigned and not notarized** for this beta.

## What the DMG contains

The DMG contains:

- `DubLocal.app` with the established DubLocal logo;
- an `Applications` shortcut for drag-and-drop installation;
- first-launch instructions;
- DubLocal and third-party license notices.

Large AI models, authenticated-site Chromium data, Demucs, Whisper models and generated media are not bundled into the DMG. They remain optional/local resources managed by DubLocal after installation.

## Install

1. Open `DubLocal-0.6.0b1-macOS-unsigned.dmg`.
2. Drag **DubLocal.app** onto **Applications**.
3. On the first launch, Control-click/right-click **DubLocal.app** and choose **Open**.
4. Confirm that you want to open the app. If macOS still blocks it, open **System Settings → Privacy & Security** and choose **Open Anyway** for DubLocal.

Do not disable Gatekeeper globally. This extra step exists because beta 1 has no Developer ID signature or Apple notarization.

## What happens on first launch

The app creates a managed local DubLocal installation under:

`~/Library/Application Support/DubLocal/app`

This is intentionally a normal Git checkout of the official `ArrowSK/dublocal` repository on `main`. The packaged beta pins the first installation to the exact revision from which the DMG was built. Keeping a real managed checkout preserves DubLocal's existing safe in-app updater and automatic restart behavior instead of creating a second packaging-specific update engine.

DubLocal then creates its private Python virtual environment inside that managed checkout and installs the core application dependencies. The first setup can therefore take a few minutes and needs an internet connection.

### Required local tools

The beta needs Git and Python 3.11–3.13. When Homebrew is already installed, DubLocal can offer to install missing Git/Python components. Otherwise macOS Command Line Tools or a compatible Python may need to be installed first.

FFmpeg is required for normal video/audio processing. When Homebrew is present, first launch can offer to install FFmpeg. DubLocal itself can still open without FFmpeg so the missing resource can be diagnosed from Settings.

Whisper and AI model assets remain opt-in through DubLocal rather than being silently installed by the beta package.

## Updates

Use **Settings → Updates → Update DubLocal**. The packaged beta deliberately keeps the same official-`main` fast-forward/repair policy already used by development installations. It does not overwrite local commits, divergent history or an unexpected remote.

After an update DubLocal uses the existing detached restart path, so the updated backend should relaunch automatically.

## Files and storage

The application bundle in `/Applications` is only the launcher/bootstrap. DubLocal keeps its managed program checkout and application state in the user's Library/home folders. Models, caches and finished outputs remain separate from the `.app` bundle and are not removed by replacing the app with a newer beta.

Settings → **Storage & Cleanup** shows these categories and protects installed models, authenticated sessions and finished outputs from temporary-file cleanup.

## Uninstall

To remove only the app launcher, quit DubLocal and delete `/Applications/DubLocal.app`.

To remove the managed program installation as well, also delete:

`~/Library/Application Support/DubLocal/app`

Do not delete the whole DubLocal application-support/cache/data area unless you intentionally also want to remove model/setup state. Finished outputs under `Downloads/DubLocal`, `Movies/DubLocal`, fallback output folders, or beside original local files are ordinary user files and should be removed only manually.

## Beta limitation

0.6.0b1 is not signed or notarized. The DMG build verifies that the generated `.app` remains unsigned so the package cannot accidentally claim a security state it does not have. Signing/notarization is a later release-hardening step.
