# Storage & Cleanup

DubLocal separates disposable working data from protected application/user data. Cleanup must never become an alternative model manager or delete finished media.

## Categories

| Category | Default policy |
| --- | --- |
| Temporary jobs | Startup cleanup after 24 hours; startup cache cap 4 GiB. Stale-job cleanup also runs after Simple queue work and at normal shutdown. |
| Translation cache | Reusable cache, automatically aged/capped by the translation cache. The manual cleanup action may clear it. |
| Installed models | Protected. Removed only through Model Manager. |
| Managed runtimes | Protected. Includes optional isolated runtimes such as Demucs/TTS environments. |
| Shared Hugging Face cache | Protected because it may be shared with other applications. |
| Authenticated website sessions | Protected. Removed only by the explicit Authenticated Websites session controls. |
| Authenticated browser runtime | Current Playwright Chromium runtime is protected. Old Chromium revisions older than 30 days may be removed only when the current revision can be identified safely. |
| Course resume manifests | Completed course state is retained for 90 days; unfinished/failed/cancelled course state for 180 days. |
| Logs | `~/.dublocal/logs/dublocal.log` rotates at 5 MiB with three previous logs retained. |
| Updater repair backups | Patch backups older than 30 days are removed; at most ten recent patches are kept. |
| Finished outputs | Protected. `Downloads/DubLocal`, `Movies/DubLocal` and fallback DubLocal output folders are never touched by cleanup. Outputs copied beside local source files are also never scanned/deleted. |

## Settings

Settings → **Storage & Cleanup** reports the current size of each known category and exposes:

- **Refresh storage usage** — recalculate category sizes.
- **Clean temporary files** — remove only temporary jobs and translation cache data, then apply normal retention rules.

The manual action refuses to run while a DubLocal job is active.

## Automatic housekeeping

Automatic housekeeping runs at startup. It may prune temporary jobs, old translation cache entries, old course manifests, old repair backups and safely-identifiable obsolete Playwright Chromium revisions.

Automatic housekeeping never deletes installed models, managed runtimes, authenticated sessions, the shared Hugging Face cache or finished user outputs.
