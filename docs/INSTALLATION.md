# Install DubLocal on macOS

This page is the careful version of the installer instructions. If you just want the short path, it is three Terminal commands and then normal use happens through **DubLocal.app**.

## What you end up with

After installation you will have:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

`DubLocal.app` starts the local service and opens it in your browser. `Stop DubLocal.app` stops the background DubLocal process.

DubLocal listens only on `127.0.0.1:7861` by default, so the UI is available on your Mac rather than exposed to your home network.

## First installation

Open Terminal and run:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

That is the only installation command you should need.

### What the installer does

The installer works through the dependencies in a predictable order:

1. Finds Python 3.11 or newer. If it is missing and Homebrew is available, DubLocal can offer to install Python 3.11.
2. Creates a private `.venv` inside the DubLocal checkout.
3. Installs the DubLocal Python package into that environment.
4. Checks FFmpeg/ffprobe, used for media inspection, subtitle extraction and transcription audio preparation.
5. Checks `whisper-cli`, used for local transcription, and can offer `brew install whisper-cpp` when Homebrew is present.
6. Does **not** download any Whisper model weights.
7. Builds the branded `.icns` icon from `assets/macos/DubLocal.svg` using macOS system tools.
8. Creates the two launcher apps in `~/Applications`.

The launcher installer intentionally stops if the branded icon cannot be generated rather than silently installing a generic icon.

## Apple Silicon and Intel Macs

Both are supported by the current transcription backend.

On Apple Silicon, DubLocal leaves whisper.cpp's normal Metal acceleration path enabled. On Intel Macs, it uses the conservative CPU path for compatibility. The same subtitle workflow is available on both; transcription speed will differ.

## Install a Whisper model only when you need one

Open **DubLocal.app**, then expand **Local transcription · Whisper**.

Choose a model and click **Install / verify model**:

| Model | Approx. size | Best use |
| --- | ---: | --- |
| Tiny | 75 MiB | Fast tests and lighter hardware |
| Base | 142 MiB | Recommended starting point |
| Small | 466 MiB | Better accuracy when you can wait longer |

The model is downloaded only after you press the button. DubLocal verifies the upstream checksum before using it.

**Remove model** deletes that model from the Mac without removing DubLocal itself.

You do not need a Whisper model to extract subtitles that already exist in the source.

## Updating DubLocal from inside the app

Once this updater version is installed, normal updates do not require Terminal.

Expand **DubLocal updates** and use the buttons in order:

1. **Check for updates** — fetches the configured GitHub upstream and compares revisions.
2. **Install update** — applies a fast-forward-only Git update and refreshes the current Python environment.
3. **Restart DubLocal** — restarts through the launcher and loads the new code.

The updater is intentionally conservative. It will refuse to continue if it sees local file changes, local-only commits or divergent Git history. It never runs a destructive reset and never overwrites developer work to make an update succeed.

GitHub is contacted only when you press **Check for updates** or **Install update**.

## Manual update fallback

If the in-app updater is unavailable, the manual path remains:

```bash
cd ~/dublocal
git pull
zsh scripts/macos/install-launcher.sh
```

Rerunning the installer refreshes the Python package, checks the external engines and recreates the launcher/icon. It does not delete installed Whisper models.

If `git pull` says local changes would be overwritten, do not use `git reset --hard` unless you know exactly what those changes are. See [Troubleshooting](TROUBLESHOOTING.md#the-updater-says-local-changes-were-detected) instead.

## Where DubLocal stores things

The cloned source code normally lives at:

```text
~/dublocal/
```

Runtime state and logs live under:

```text
~/.dublocal/
```

The main launcher log is:

```text
~/.dublocal/logs/dublocal.log
```

Whisper model weights are stored outside the Git repository in the normal macOS application-data location selected by `platformdirs`. That keeps Git updates separate from models and future projects.

## Uninstalling

For the current development-stage install, remove the launcher apps and checkout only if you no longer need them:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
~/dublocal/
```

Optional model data and runtime logs live separately, so deleting the repository alone does not silently delete large downloaded models. A proper packaged uninstaller is planned for the release stage.

## Next

For day-to-day use, continue with the [User Guide](USER_GUIDE.md). If something fails, use [Troubleshooting](TROUBLESHOOTING.md) before reinstalling anything.
