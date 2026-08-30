# Output profile design rationale

This note records why DubLocal treats output format, persistent profile and per-job resolution as separate decisions.

The previous export policy attached a fixed quality-first bitrate to each resolution. That was simple internally but inappropriate for a product that offers both preservation-oriented MKV and explicitly Shareable MP4: a 480p Shareable export could still be encoded at 2.5 Mbps video + 192 kbps audio.

Beta 5 therefore makes **Auto format-aware** rather than pretending one compression policy fits every output:

- MKV Auto preserves the source video whenever practical.
- MP4 Auto uses Balanced compatibility/size targets.
- Shareable MP4 Auto uses Compact transfer targets.

Users who disagree with Auto can persistently choose Original, High, Balanced or Compact separately for each format in Settings. The Standard workflow remains compact and exposes only a Resolution limit as an optional job-specific ceiling.

The engine may copy an existing video stream when it already satisfies the selected output policy. It may re-encode when resolution, codec/pixel compatibility or bitrate would defeat that policy. Burned subtitles always require video encoding because text must become part of the picture.

The policy is intentionally expressed as profiles rather than raw bitrate boxes. Raw codec controls belong in implementation/advanced tooling, while normal product settings should state the user's intent: preserve, quality first, balance, or compact transfer.
