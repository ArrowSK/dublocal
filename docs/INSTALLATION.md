# Installing DubLocal on macOS

DubLocal is designed to behave like a normal local Mac app after its first installation. The repository remains the source of truth, while a native launcher is installed into `~/Applications`.

## Requirements

- macOS 13 or newer is the initial support target.
- Python 3.11 or newer.
- Internet access during the initial Python package installation.
- FFmpeg/ffprobe for local media inspection, subtitle extraction and transcription-audio preparation.
- `whisper.cpp` / `whisper-cli` for M2 local transcription.

The installer can bootstrap Python with Homebrew when needed and can offer to install FFmpeg and whisper.cpp when Homebrew is already present. Apple Silicon and Intel Macs are both supported by the M2 backend; Apple Silicon keeps whisper.cpp Metal acceleration enabled, while Intel uses the conservative CPU path.

## Install

Clone the repository, enter it, then run the launcher installer:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer:

1. finds Python 3.11+ and can offer Homebrew Python when missing;
2. creates `.venv` inside the repository if necessary;
3. installs/refreshes DubLocal in that environment;
4. checks for FFmpeg/ffprobe and can offer `brew install ffmpeg`;
5. checks for `whisper-cli` and can offer `brew install whisper-cpp`;
6. does **not** download Whisper model weights;
7. generates the macOS `.icns` icon from the original `assets/macos/DubLocal.svg` artwork using macOS system tools;
8. creates `~/Applications/DubLocal.app`;
9. creates `~/Applications/Stop DubLocal.app`.

The installer intentionally aborts if the branded icon cannot be generated rather than silently installing a generic app icon.

## Install a Whisper model

Launch DubLocal and open the **Local transcription · Whisper** panel. Choose one of the allowlisted multilingual models and click **Install / verify model**:

- Tiny — 75 MiB, fastest;
- Base — 142 MiB, recommended starting point;
- Small — 466 MiB, better accuracy but slower/larger.

Models are downloaded only after this explicit action, are stored outside the Git repository under the user's normal macOS application-data location, and are checksum-verified before use. **Remove model** deletes the selected local model without affecting DubLocal itself.

The app remains usable for existing-caption extraction when no Whisper model is installed.

## Using the launcher

Open `DubLocal.app` from `~/Applications` or drag it into the Dock.

The launcher uses `127.0.0.1:7861`, deliberately separate from NarRoam Studio's local port. It offers:

- `Launch / Open` — open the existing local instance or start one;
- `Stop All & Launch` — stop any DubLocal processes and start a clean instance;
- `Cancel`.

If the Git revision has changed since the running process started, the launcher recommends `Stop All & Launch` so the updated code is used.

`Stop DubLocal.app` stops all DubLocal instances.

## Local files

Runtime state and logs are stored under:

```text
~/.dublocal/
```

The main log is:

```text
~/.dublocal/logs/dublocal.log
```

Whisper models are stored in the macOS application-data directory selected by `platformdirs`; they are intentionally not stored inside the cloned repository.

## Updating

From the cloned repository:

```bash
git pull
zsh scripts/macos/install-launcher.sh
```

Rerunning the installer refreshes the Python package, checks external engines, and recreates the launcher/icon without deleting installed Whisper models or future user projects.

The current installer no longer changes executable bits on tracked repository scripts, so running it should not dirty the Git working tree.
