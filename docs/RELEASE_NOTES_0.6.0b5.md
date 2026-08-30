# DubLocal 0.6.0b5

Beta 5 makes media export behave like a finished product rather than a collection of codec switches.

The immediate trigger was a real 480p Shareable MP4 that came out at roughly 160 MB for a short video. The old export ladder used 2.5 Mbps at 480p, 5 Mbps at 720p and up to 25 Mbps at 4K, plus 192 kbps AAC. Those values were reasonable as conservative quality-first transcodes, but not for something explicitly labelled Shareable.

## Format-aware output profiles

DubLocal now has persistent **Settings → Output profiles** for each output family:

- **MKV**
- **MP4**
- **Shareable MP4**

Each format can use **Auto**, **Original**, **High**, **Balanced** or **Compact**.

Auto is deliberately different by format:

- **MKV Auto → Original**: preserve the source video whenever practical. MKV remains the preservation-oriented multi-track output.
- **MP4 Auto → Balanced**: use a compatible H.264-oriented export, up to 1080p, and re-encode when the source is incompatible or materially larger than the target.
- **Shareable MP4 Auto → Compact**: cap at 720p and use a much smaller sharing-oriented bitrate. Burned subtitles use the same profile.

An explicit Resolution limit in the Standard workflow remains available under Options and acts as an additional ceiling; it is no longer treated as the compression policy itself.

## Smarter size targets

The old 480p Shareable target was 2.5 Mbps video + 192 kbps audio. Auto Shareable now targets approximately:

- 480p: 500 kbps H.264 + 96 kbps AAC — about **4.5 MB/minute**
- 720p: 900 kbps H.264 + 96 kbps AAC — about **7.5 MB/minute**

This does not pretend that a multi-minute 480p video can remain watchable at 5 MB total. Instead, DubLocal gives predictable, realistic file sizes while keeping High/Balanced/Original available when quality or preservation matters more than transfer size.

The engine also avoids unnecessary re-encoding: when an existing compatible stream is already at or below the selected target, it can be copied rather than encoded again. Conversely, MP4/Shareable output is re-encoded when the source codec, pixel format, resolution or bitrate would defeat the selected profile.

## Product terminology and UI

The primary consumer workflow is now called **Standard workflow** rather than “Magic Flow”. The main action is **Start Processing**, and the former Simple tab is **Standard**.

Other production-facing labels were tightened at the same time:

- **Outputs** instead of “Create”
- **Options** instead of “More options”
- **Output files** instead of “Results”
- **Resolution limit** instead of the ambiguous “Video quality” control
- **Audio & delivery** instead of “Audio, voice & sharing”

Internal compatibility names remain unchanged where renaming them would add migration risk; the product UI no longer exposes those implementation names.

## Validation

Regression coverage verifies that:

- Auto resolves independently for MKV, MP4 and Shareable MP4;
- 480p Shareable Auto uses the compact 500/96 kbps targets;
- large Shareable sources are capped at 720p;
- MKV Auto preserves the source unless a lower resolution is explicitly requested;
- MP4 Auto re-encodes oversized or incompatible video;
- saved per-format profiles override Auto;
- the production UI exposes Standard workflow, Start Processing, Output profiles and Resolution limit without the old “Magic Flow” label.

The existing beta-3 adaptive translation and beta-4 subtitle-capable FFmpeg behavior remain in place.

## Updating

Existing packaged beta users can use **Settings → Updates → Update DubLocal**.

New users can download `DubLocal-0.6.0b5-macOS-unsigned.dmg` from this release.

The beta remains unsigned and not notarized, so macOS may require **Open Anyway** on first launch.
