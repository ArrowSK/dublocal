# DubLocal 0.6.0b3

Beta 3 focuses on making contextual translation practical for longer videos and movies without giving back the subtitle-alignment safety added in beta 2.

Beta 2 deliberately reduced fragmented-caption jobs to small batches after a real YouTube translation could lose subtitle IDs. That was safe, but it also meant a clean nine-minute single-speaker video could spend several minutes repeatedly feeding the same programme context to Qwen.

## What changed

- Qwen3 8B now starts with up to **48 subtitle lines per model call**. Qwen3 4B starts with up to **36**.
- Every large response is still checked for exact subtitle IDs, order, target-language script and output validity before it is accepted.
- If a large batch fails that strict check, DubLocal does **not** run the expensive whole-batch repair path immediately. It retries only that section at half size.
- The safety floor remains **12 lines**. At that point the existing bounded missing-ID/format recovery logic is used.
- After two clean smaller batches, DubLocal grows the batch size again. A difficult section therefore does not condemn the rest of a long movie to the slowest setting.
- When a failed fast attempt reaches the recovery floor, its model output is reused instead of performing another identical generation first.
- Programme-wide and nearby context remain independent from the output batch size, so the speed improvement does not turn translation into isolated sentence-by-sentence work.
- Progress now reports how many subtitles are complete and the next adaptive batch ceiling.
- Translation cache policy changed so beta-2 cache entries are not mixed with this execution strategy.

## Why this should be faster

Local Qwen inference has to process the prompt context for every model request. When a video is split into dozens of tiny batches, the same several-thousand-token context is repeatedly prefetched. Clean 48-line batches substantially reduce the number of those requests. If Qwen proves unreliable on a particular section, DubLocal falls back locally rather than forcing every section to be small from the start.

This release does not claim a fixed movie translation time because performance still depends on Mac model, RAM, selected Qwen model, subtitle density, source/target language and whether the optional senior review pass is enabled.

## Validation

Regression tests cover a clean 96-subtitle timeline completing as two 48-line model calls and a deliberately malformed first 48-line response falling back to 24-line batches before automatically growing back to 48.

The alignment safety rule is unchanged: if DubLocal cannot establish a trustworthy mapping from every translated line to the original subtitle timeline, it stops rather than writing a shifted/corrupted SRT.

## Updating

Existing packaged beta users can use **Settings → Updates → Update DubLocal**.

New users can download `DubLocal-0.6.0b3-macOS-unsigned.dmg` from this release.

The beta remains unsigned and not notarized, so macOS may require **Open Anyway** on first launch.