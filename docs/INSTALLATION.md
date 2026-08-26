# Installing DubLocal on macOS

DubLocal is designed to behave like a normal local Mac app after its first installation. The repository remains the source of truth, while a native launcher is installed into `~/Applications`.

## Requirements

- macOS 13 or newer is the initial support target.
- Python 3.11 or newer.
- Internet access during the initial Python package installation.
- FFmpeg/ffprobe for local media inspection and extraction. The installer can offer to install FFmpeg through Homebrew when Homebrew is already present.

Apple Silicon and Intel Macs are both intended to be supported. Later AI backends may have different performance characteristics.

## Install

Clone the repository, enter it, then run the launcher installer:

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer:

1. finds Python 3.11+;
2. creates `.venv` inside the repository if necessary;
3. installs/refreshes DubLocal in that environment;
4. checks for FFmpeg/ffprobe;
5. generates the macOS `.icns` icon from the original `assets/macos/DubLocal.svg` artwork using macOS system tools;
6. creates `~/Applications/DubLocal.app`;
7. creates `~/Applications/Stop DubLocal.app`.

The installer intentionally aborts if the branded icon cannot be generated rather than silently installing a generic app icon.

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

## Updating

From the cloned repository:

```bash
git pull
zsh scripts/macos/install-launcher.sh
```

Rerunning the installer refreshes the Python package and recreates the launcher/icon without deleting future optional models or user projects stored outside the repository.
