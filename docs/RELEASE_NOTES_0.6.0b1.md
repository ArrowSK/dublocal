# DubLocal 0.6.0b1

This is the first packaged macOS beta of DubLocal.

The goal of this release is simple: you should be able to download a normal DMG, drag DubLocal to Applications and use the same local-first subtitle/translation/dubbing workflow without setting the project up from source first.

## What is in this beta

- **Magic Flow** for YouTube, local files and supported authenticated course/website sources.
- Local Whisper transcription and hardware-aware contextual translation.
- Local voice-over with Kokoro and supported additional providers.
- Multi-track media export, including original audio/subtitle preservation where compatible.
- Sequential queues for multiple files, YouTube collections and course lessons.
- In-app model management, storage/cleanup and guarded Git-based updates.
- A proper DubLocal macOS app icon and matching in-app branding.
- A normal drag-to-Applications DMG.

## Important first-beta limitation

The app is **unsigned and not notarized**.

On first launch, macOS may block it. Control-click/right-click **DubLocal.app → Open**. If it is still blocked, use **System Settings → Privacy & Security → Open Anyway** for DubLocal.

Do not disable Gatekeeper globally.

## First launch

The package is intentionally small. Large AI models are not bundled.

On first launch DubLocal prepares a managed installation under:

```text
~/Library/Application Support/DubLocal/app
```

It also creates its private Python environment. Git and a compatible Python 3.11–3.13 are required for this first beta; when Homebrew is already present, DubLocal can offer to install missing components. FFmpeg is required for normal media processing and can also be installed through Homebrew when available.

## Download integrity

The release includes the DMG and a matching `.sha256` file.

## Documentation

- [Install the beta](BETA_INSTALLATION.md)
- [User Guide](USER_GUIDE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Documentation hub](README.md)

This remains a beta: the processing pipeline is substantially developed, but packaging, wider real-world hardware validation and Apple signing/notarization still need field testing and hardening.
