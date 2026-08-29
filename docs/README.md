# DubLocal documentation

If you arrived here because you simply want to use DubLocal, you probably do not need to read everything in this folder.

Start with the job in front of you:

| I want to… | Read this |
| --- | --- |
| Install the macOS beta | [Beta installation](BETA_INSTALLATION.md) |
| Dub, translate or subtitle a video | [User Guide](USER_GUIDE.md) |
| Fix something that is not working | [Troubleshooting](TROUBLESHOOTING.md) |
| Understand what is taking disk space | [Storage & Cleanup](STORAGE_CLEANUP.md) |
| Use a signed-in course/website | [Authenticated websites](AUTHENTICATED_WEBSITES.md) |
| Understand or add voices | [TTS providers](TTS_PROVIDERS.md) |
| Develop DubLocal | [Installation from source](INSTALLATION.md) + [Architecture](ARCHITECTURE.md) |

## For normal users

### [Beta installation](BETA_INSTALLATION.md)

The short, practical path from DMG to a running DubLocal. It explains the one-time unsigned-app warning, what first launch installs, where the managed application lives, updates and uninstall behavior.

### [User Guide](USER_GUIDE.md)

Use this when Magic Flow is not self-explanatory or when you want to understand Simple vs Advanced mode, subtitle selection, local translation, voice-over, media export and course jobs.

### [Troubleshooting](TROUBLESHOOTING.md)

Organized by the stage that failed. The guiding rule is simple: fix the broken stage rather than wiping models, caches or the whole installation.

### [Storage & Cleanup](STORAGE_CLEANUP.md)

Explains the difference between disposable job data and things DubLocal deliberately protects, such as installed models, signed-in browser sessions and finished user outputs.

### [Authenticated websites](AUTHENTICATED_WEBSITES.md)

Explains how dedicated local browser sessions work, what gets saved, how course selection/resume behaves, and where DubLocal draws the line around DRM/encrypted media.

### [TTS providers](TTS_PROVIDERS.md)

Language/provider coverage, built-in local voices and the custom-provider contract.

## For people who want to understand the internals

### [Architecture](ARCHITECTURE.md)

The main processing layers, module boundaries, job flow and safety assumptions.

### [Audio architecture](AUDIO_ARCHITECTURE.md)

How DubLocal handles generated speech timing, soundtrack reduction, multi-track output and optional Demucs separation.

### [Batch queue & updates](BATCH_QUEUE_AND_UPDATES.md)

Sequential queueing, cancellation, Git-based updates and restart behavior.

### [Quality notes](QUALITY_NOTES.md)

Why transcription/translation quality decisions are intentionally conservative and where heuristics are used.

### [Production readiness](PRODUCTION_READINESS.md)

What has been hardened already and what still counts as beta/validation work.

### [UX notes](UX_NOTES.md)

The reasoning behind Simple/Advanced separation and the application's current interaction model.

## Historical / implementation notes

`M5_3_STABILIZATION.md` records a specific stabilization milestone. It remains useful for project history and regression context, but it is not required reading for normal use.

## One important distinction

DubLocal is local-first, not offline-only.

The speech recognition, translation, voice generation and media-processing pipeline is designed to run on the Mac once its optional models/runtime assets are present. Network access is still naturally required for things such as YouTube downloads, GitHub updates, model/runtime downloads and signing into an authenticated source website.

That distinction is intentional: local processing without pretending that network sources are somehow offline.
