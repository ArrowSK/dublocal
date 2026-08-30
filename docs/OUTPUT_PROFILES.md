# Output profiles

DubLocal separates **format**, **profile** and **resolution limit** so users do not have to reason about codec bitrates for ordinary jobs.

## Format

The output format describes the kind of file you want:

- **MKV** — preservation-oriented and best for multiple selectable tracks.
- **MP4** — broadly compatible output.
- **Shareable MP4** — compact H.264/AAC output intended for messaging and ordinary transfer.

## Profile

Profiles are persistent defaults under **Settings → Output profiles**. Each format has its own setting:

- **Auto · format-aware**
- **Original · preserve source video**
- **High · quality first**
- **Balanced · good quality / smaller file**
- **Compact · sharing / storage**

Auto deliberately resolves differently for each format:

| Format | Auto resolves to | Purpose |
| --- | --- | --- |
| MKV | Original | Preserve source video whenever practical |
| MP4 | Balanced | Compatible output with sensible size/quality trade-off, up to 1080p |
| Shareable MP4 | Compact | Predictable transfer size, up to 720p |

## Resolution limit

The Standard workflow exposes **Resolution limit** under **Options**. It is an optional per-job ceiling. It does not replace the saved profile.

For example, Shareable MP4 on Auto already uses Compact. Choosing a 480p Resolution limit additionally caps the picture at 480p; the Compact bitrate policy remains in effect.

## Current H.264 targets

Approximate target bitrates:

| Profile | 480p | 720p | 1080p | Audio |
| --- | ---: | ---: | ---: | ---: |
| Compact | 500 kbps | 900 kbps | 1.5 Mbps | 96 kbps AAC |
| Balanced | 800 kbps | 1.4 Mbps | 2.6 Mbps | 128 kbps AAC |
| High | 1.2 Mbps | 2.3 Mbps | 4.3 Mbps | 160 kbps AAC |

At 480p, Compact is about **4.5 MB per minute** including audio before small container overhead. Actual output varies with duration and stream/container details.

## When DubLocal re-encodes

DubLocal avoids unnecessary work where it can. Original/preservation output normally copies the source video stream. Other profiles may re-encode when a source exceeds the profile resolution/size target or is not suitable for the requested compatible MP4 output.

Burned subtitles necessarily require video encoding because subtitle pixels must be rendered into every affected frame. They still use the same Shareable MP4 profile selected in Settings.
