# DubLocal 0.6.0b2

Beta 2 is a focused reliability update for contextual subtitle translation.

The first packaged beta could fail on otherwise ordinary YouTube videos when automatic captions were split into many short fragments. Qwen could translate the material but occasionally vary or omit the requested subtitle-ID formatting; DubLocal's recovery path then stopped the whole job rather than risk writing a shifted/corrupted SRT.

## What changed

- Fragmented subtitle timelines now use smaller translation batches. Very dense automatic-caption timelines are capped at 12 target lines per model call instead of being pushed through 36–48-line batches.
- Programme context remains long-form and hardware-aware; the smaller batches change output alignment work, not the amount of useful translation context available to Qwen.
- Output recovery accepts additional common Qwen formatting variants such as `1. text` and `ID 2: text`, while still requiring explicit numeric alignment where IDs are present.
- A complete ID-less response can be recovered by position only when its number of clean lines exactly equals the number of requested subtitles. DubLocal never guesses a shifted mapping.
- Missing-ID recovery now sends Qwen only the source lines that are actually missing, plus compact continuity context, instead of distracting it with the complete chunk again.
- Translation cache protocol versioning was bumped so older cached results are not mixed with the new chunk/recovery policy.

## Safety boundary unchanged

DubLocal still refuses to write an SRT when subtitle alignment cannot be established safely. The fix makes recovery substantially more tolerant of harmless model formatting differences without weakening that rule.

## Updating

Existing packaged beta users can use **Settings → Updates → Update DubLocal**. The managed installation will update and restart through the packaged bootstrap.

New users can download the `DubLocal-0.6.0b2-macOS-unsigned.dmg` attached to this release.

The beta remains unsigned and not notarized, so macOS may require **Open Anyway** on first launch.
