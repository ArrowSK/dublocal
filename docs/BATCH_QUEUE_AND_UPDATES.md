# DubLocal batch queue and app updates

**Applies to the current v0.6.0.dev0 development build.**

This document describes the Simple-mode queue and the simplified updater. The existing Advanced workflow and processing engines are unchanged.

## One normal update action

Settings → Updates now presents one primary action: **Update DubLocal**.

The action performs the normal application lifecycle in one operation:

1. check the official `ArrowSK/dublocal` `main` branch;
2. verify that the managed checkout is safe to update;
3. fast-forward to the newest revision when an update exists;
4. refresh the DubLocal Python environment;
5. automatically restart DubLocal when the installed core changed.

If tracked DubLocal program files were modified accidentally, the same action uses the existing repair path. It saves a patch backup before restoring the managed program files. It does not erase untracked user files.

The one-action updater deliberately refuses to rewrite a different Git history. A non-`main` branch, local commits that are ahead of GitHub, a diverged checkout, or a nonstandard upstream remains a manual/developer case.

The older Check / Install / Repair / Restart controls are no longer part of the visible consumer UI. Their proven underlying updater functions remain in place and are reused by the single action.

## One Simple queue for one or many sources

Main → Simple still uses Magic Flow. The processing pipeline itself is not duplicated or replaced.

A source is first expanded into a queue. Every queue item is then passed through the existing `run_magic_flow` engine. Items are processed strictly one at a time.

There are two separate protections against parallel work:

- the batch runner waits for one Magic Flow item to finish before starting the next;
- the Gradio application queue continues to use `default_concurrency_limit=1`.

A failure in one item is recorded in the queue results and does not delete successful outputs or stop later items.

## Local files

Choose **Local file** and select one or several audio/video files in the same file picker.

Duplicate selections are removed by resolved path while preserving the original selection order.

The same Magic Flow settings apply to every selected file. For example, one selection of Russian + Subtitles + Translate + Voice-over + Media applies to the entire queue.

Finished persistent copies are written beside each original source file. This makes subtitle sidecars easy to find and keeps outputs associated with the correct source rather than putting a whole batch into one unrelated folder.

Typical layout:

```text
Holiday 01.mp4
Holiday 01.en.srt
Holiday 01.ru.srt
Holiday 01.voice.ru.wav
Holiday 01.dub.ru.mkv

Holiday 02.mp4
Holiday 02.en.srt
Holiday 02.ru.srt
Holiday 02.voice.ru.wav
Holiday 02.dub.ru.mkv
```

The normal in-app Results files still come from DubLocal's temporary job cache. Therefore DubLocal does not expose arbitrary source folders through Gradio just to make the download widgets work.

## YouTube video, playlist, or channel

The same YouTube field accepts:

- a single watch/short/live video URL;
- an explicit playlist URL;
- a YouTube channel URL that yt-dlp can enumerate.

A normal watch URL remains one video even when YouTube has appended a `list=` parameter. To intentionally process the whole playlist, paste the playlist URL itself. This avoids accidentally turning a single-video job into a large batch.

For a playlist or channel, DubLocal uses a lightweight yt-dlp enumeration pass first. It does not download every video during enumeration. Processable entries are converted to individual video queue items in source order. Duplicate IDs are removed; unavailable/private/deleted entries that yt-dlp cannot enumerate are skipped.

Bare channel forms such as `https://www.youtube.com/@handle` are normalized to the channel's videos feed before enumeration. Channel support therefore follows what the installed yt-dlp version can reliably expose; YouTube can change its site behaviour independently of DubLocal.

Each enumerated video then goes through the same single-video Magic Flow path that was already used before batch support.

Persistent YouTube copies are stored under:

```text
~/Downloads/DubLocal/
```

The Results accordion also exposes the generated files from the normal DubLocal job cache.

## Queue progress and results

The main progress display reports both the overall queue position and the current item's Magic Flow stage, for example:

```text
3/12 · Interview part 3 · Translating with contextual model
```

When processing finishes, Results contains the grouped subtitle, translated subtitle, voice and media files plus a queue table showing each item's final state and its persistent output location or error.

## What remains intentionally unchanged

Batch support is a Simple-mode orchestration layer. It does not alter:

- subtitle-source recommendation;
- Whisper transcription behaviour;
- contextual translation;
- Kokoro/provider selection;
- native TTS timing;
- music-aware source separation and mixing;
- video-quality/export rules;
- the Advanced one-source stage-by-stage workflow.

This separation is deliberate: batching changes how jobs are supplied and sequenced, not how an individual DubLocal job is processed.
