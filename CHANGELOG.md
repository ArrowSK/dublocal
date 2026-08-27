# DubLocal changelog

DubLocal is still in active development. Versions below describe development builds from `main`.

> **Current development build:** `v0.5.1.dev0` — **Voice Match + Dub Mix + Subtitle/Quality Export Refinement**
>
> There is no packaged GitHub Release yet. The first packaged release will be published after Mac distribution/release validation is ready.

## v0.5.1.dev0 — Voice Match + Dub Mix + Subtitle/Quality Export Refinement — current

This refinement keeps the v0.5 workflow intact and changes only the affected Voice-over and Export behavior.

### Automatic voice matching

- **Auto · match original vocal range** is now the normal Main voice choice.
- DubLocal performs a lightweight local acoustic pass over the original audio and chooses lower/higher Kokoro voice presets per subtitle segment.
- If the source alternates between clearly lower and higher vocal ranges, Kokoro can switch between two voices segment-by-segment without loading a second TTS model.
- The analysis is a practical acoustic preset selector, not speaker identity or gender-identity detection. A subtitle line containing overlapping speakers still receives one TTS voice.
- Languages with only one available Kokoro voice gracefully fall back to that voice.

### Stronger source-dialogue suppression

- Export no longer relies only on the generated voice waveform to trigger ducking.
- The source subtitle timeline now acts as the dialogue/singing guide, so the original vocal stays suppressed for the whole spoken/sung source window even if the translated TTS line is shorter.
- Closely spaced dialogue windows are merged and use fast attack / controlled release to avoid obvious level pumping.
- The fallback sidechain path is also stronger when no usable timed dialogue guide exists.
- This remains a consumer-source compromise. Professional dubbing ideally uses dialogue-free Music & Effects stems; DubLocal still does not claim true dialogue/source separation.

### Selectable subtitle tracks inside the exported media

- Generated original and translated SRTs are embedded by default when available.
- They remain selectable subtitle streams for players such as VLC; they are not burned into the picture.
- MKV also preserves existing source subtitle streams. MP4 packages generated DubLocal subtitle tracks as `mov_text` without video re-encoding.
- Original and translated tracks receive language/title metadata; the translated DubLocal track is marked default when present.

### Video quality selection

- Export now offers **Original / best available**, 2160p, 1440p, 1080p, 720p and 480p maximum options.
- YouTube quality selection chooses an appropriate source format before download; DubLocal still stream-copies that selected video during remux.
- Local files remain **Original / no re-encode** by default.
- Choosing a lower quality for a local video is an explicit opt-in to H.264 VideoToolbox re-encoding; DubLocal never downscales a local file silently.

## v0.5.0.dev0 — M5 Local Dubbed Media Export

v0.5 connects the existing subtitle, translation and voice stages into the first practical end-to-end dubbed-media workflow while keeping the normal UI progressive and local-first.

### Workflow fixes before M5

- Whisper/extracted-track language metadata now accepts both ISO codes and full language names and is carried into **Translate → From** automatically when detected.
- A newly loaded source clears stale language state from the previous job.
- If auto-detection genuinely cannot identify the source language, translation stops with a precise request to choose it manually instead of failing ambiguously.
- User-facing subtitle filenames now derive from the loaded media name with a language suffix, for example `Movie Name.en.srt`, `Movie Name.es.vtt` and translated `Movie Name.ru.srt`.
- Closed-caption cues remain in subtitle exports but are removed from the temporary TTS input. Standalone `[MUSIC]`/`[APPLAUSE]` rows become silent; inline cues such as `[LAUGHS] Hello` speak only `Hello`.
- Contextual translation prompts/review now explicitly handle discourse-level gender/reference, idioms/phraseologisms and metaphors instead of relying on generic “use context” wording.
- The translator is instructed not to invent unsupported gender when context is ambiguous and not to flatten or invent metaphorical imagery.
- The senior review pass checks gender/reference consistency, idiomatic equivalence, metaphor fidelity, grammar, terminology continuity and register.
- v0.4.2 CI regression expectations are corrected: the prompt explicitly contains a **do not invent** rule and wrong-script validation reports `unexpected non-target script`.

### M5 timing

- Reads the M4 per-segment Kokoro timing manifest.
- For an overflowing voice line, DubLocal first borrows real silence up to the next spoken segment.
- If more fitting is needed, FFmpeg `atempo` speeds only that segment, capped at 1.25×.
- Speech is never truncated merely to hit the subtitle boundary.
- Any line that still cannot fit is reported in the final stage status.

### M5 soundtrack mix

- Builds a new dubbed soundtrack from the original primary audio plus synchronized voice.
- Sidechain compression ducks the source soundtrack while DubLocal speech is present.
- The result is mixed/limited and encoded as AAC 192 kbit/s stereo.
- This is ordinary ducking/overlay, **not** dialogue/background source separation; original dialogue can remain quietly audible underneath.

### M5 output modes

- **Replace primary audio — default:** DubLocal's mixed track becomes the first/default audio stream; additional original audio tracks are retained where possible.
- **Add dubbed audio as second track:** every original audio track remains untouched and the DubLocal mix is appended as another selectable track.
- Dubbed tracks receive language/title metadata.
- MKV is the recommended output container for maximum stream compatibility.
- MP4 is supported only when the selected source streams can be remuxed compatibly.

### No unnecessary video encoding

- Video uses FFmpeg stream-copy (`-c:v copy`) whenever a video stream is present.
- DubLocal never silently re-encodes an incompatible video just because MP4 was selected; it asks the user to choose MKV instead.
- This preserves original video quality and avoids long unnecessary renders.

### Temporary data

- YouTube source copies used for M5, fitted voice segments, intermediate mixes and remux outputs stay inside the normal DubLocal jobs cache.
- Existing automatic cleanup remains: 24-hour age limit and 4 GiB cache cap.

## v0.4.2.dev0 — Subtitle Export + Translation Quality Pass

- Made subtitle output first-class: SRT default with VTT/TXT conversion without rerunning transcription.
- Added optional Accurate Large-v3-Turbo-Q5 Whisper model for difficult source audio.
- Added hardware-aware **Recommended for this Mac** contextual translation profiles.
- Low-memory Apple Silicon uses Qwen3 4B with reduced llama.cpp context allocation; stronger Macs use Qwen3 8B, with a senior review pass on the Best-quality profile.
- Kept legacy OPUS as an explicit small/fast option.
- Added protected subtitle tags, runtime/prompt leakage rejection, wrong-script validation and strict subtitle-ID/timestamp integrity.
- Added persistent workflow stage states and hardware explanation under engine details/Model Manager rather than cluttering Main.

## v0.4.1.dev0 — M3.1 Contextual Translation

Introduced the first Qwen3 contextual translation path with nearby dialogue, programme-wide source context and rolling translated terminology/style memory. Real-language testing showed that Qwen3 4B alone was not a universal top-quality choice, which led to the adaptive 4B/8B v0.4.2 architecture.

## v0.4.0.dev0 — M4 Local Voice

- Added Kokoro as the first local TTS backend.
- Reused compatible existing Kokoro environments through isolated worker processes.
- Added local voice-only WAV generation from source or translated SRT.
- Added per-segment assets, timing manifest and overflow diagnostics.
- Kept source soundtrack modification deliberately out of M4; M5 now consumes that manifest.

## v0.3.0.dev0 — M3 Local Translation

- Added pinned local Helsinki-NLP OPUS/Marian subtitle translation.
- Preserved timestamps and side-by-side subtitle review.
- Added shared Hugging Face cache and compatible external runtime reuse.

## v0.2.0.dev0 — M2 Local Transcription

- Added local `whisper.cpp` transcription.
- Added model management, language selection/detection and timestamped SRT output.
- Added YouTube/local-file transcription fallback and the first in-app updater.

## v0.1.0.dev0 — M1 Source and Captions

- Added local media inspection with ffprobe.
- Added YouTube metadata/caption discovery with yt-dlp.
- Added existing subtitle/caption extraction and the branded macOS launcher.