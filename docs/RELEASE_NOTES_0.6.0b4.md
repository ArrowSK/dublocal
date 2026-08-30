# DubLocal 0.6.0b4

Beta 4 is a focused macOS export reliability update discovered while running the same real YouTube workflow used to validate beta 3.

Translation completed and the standalone SRT was available, but **Burn subtitles into Shareable MP4** failed with:

```text
Error opening output files: Filter not found
```

## Root cause

This was not an H.264 encoder failure. DubLocal was invoking FFmpeg's `subtitles` video filter, but the installed FFmpeg build did not contain that libass-backed filter.

The old fallback then changed `h264_videotoolbox` to `libx264` and retried the same filter graph. That could never fix a missing filter, so it spent time on a second attempt and returned a misleading "software H.264 fallback failed" message.

## What changed

- Burn-in now checks the exact FFmpeg binary for the `subtitles` filter before starting the encode.
- Normal FFmpeg is used when it already supports subtitle rendering.
- If normal FFmpeg lacks the filter, DubLocal looks for the keg-only Homebrew `ffmpeg-full` binary, including standard Apple Silicon and Intel locations and a custom Homebrew prefix.
- Packaged setup/update can offer to install `ffmpeg-full` side-by-side. It does not uninstall or replace normal FFmpeg.
- The VideoToolbox → `libx264` retry remains available for genuine encoder failures.
- A missing-filter error no longer triggers a pointless second H.264 encode attempt.
- If no subtitle-capable FFmpeg exists, DubLocal reports the actual missing capability and preserves the standalone SRT.

## Why there are two FFmpeg builds

DubLocal's ordinary audio/video pipeline can use the normal Homebrew FFmpeg package. Burned subtitle rendering needs additional subtitle/font libraries that are not guaranteed to be present there. Homebrew's `ffmpeg-full` package includes libass and is keg-only, so it can live alongside the normal FFmpeg installation without taking over the rest of DubLocal.

## Validation

Regression tests cover:

- choosing normal FFmpeg when it exposes the subtitle filter;
- falling back to the side-by-side `ffmpeg-full` binary when normal FFmpeg lacks it;
- refusing to start a burn-in encode when no candidate has the required filter;
- retrying the same subtitle-capable FFmpeg with `libx264` after a genuine VideoToolbox encoder failure;
- the exact `Filter not found` class of failure without making a second encode attempt;
- packaged bootstrap detection and optional `ffmpeg-full` preparation without removing normal FFmpeg.

## Updating

Existing packaged beta users can use **Settings → Updates → Update DubLocal**.

During the beta-4 update, DubLocal may ask once whether it may install the optional subtitle-capable `ffmpeg-full` build. Accept this if you want **Burn subtitles into Shareable MP4**.

New users can download `DubLocal-0.6.0b4-macOS-unsigned.dmg` from this release.

The beta remains unsigned and not notarized, so macOS may require **Open Anyway** on first launch.
