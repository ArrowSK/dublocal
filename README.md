<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, contextual translation, AI voice-over and dubbed-media export for macOS.<br>
  Your processing stays on your Mac.
</p>

<p align="center">
  <strong>Current development build: v0.5.0.dev0 · M5 Local Dubbed Media Export</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal turns a YouTube link or local media file into a timed subtitle timeline. You can stop with subtitles, translate them locally, generate a local voice track, or continue through M5 to a dubbed MKV/MP4 without needlessly re-encoding the video.

The interface stays intentionally simple:

- **Main** — Source → Subtitles → Translate → Voice-over → Export.
- **Settings** — Updates, Model Manager and Local Resources.

There is currently no packaged DMG/GitHub Release. Development builds are updated from official `main` inside the app.

## What works now

| Stage | Status | What DubLocal does |
| --- | --- | --- |
| Media input | ✅ | YouTube URL or local video/audio |
| Existing subtitles | ✅ | Finds/extracts supported caption tracks |
| Local transcription | ✅ | Timestamped subtitles through `whisper.cpp` |
| Subtitle download | ✅ | SRT default, plus VTT/TXT; translation optional |
| Contextual translation | ✅ | Hardware-aware Qwen3 4B/8B through `llama.cpp` |
| Fast legacy translation | ✅ | OPUS sentence-level path remains optional |
| AI voice | ✅ | Kokoro voice-only track; bracketed caption cues stay silent |
| Timing fit | ✅ M5 | Borrow silence, then modestly speed overflowing speech |
| Soundtrack mix | ✅ M5 | Duck original soundtrack under translated speech |
| Media export | ✅ M5 | Replace primary audio or add dubbed audio as another track; video stream-copy where compatible |

## The normal workflow

1. **Load source.** Choose YouTube or Local file and click **Load source**. The Source card confirms what is loaded.
2. **Get subtitles.** Use an existing track or transcribe locally. DubLocal carries the detected subtitle language forward automatically when Whisper/track metadata provides it.
3. **Stop here if you only need subtitles.** The file is downloadable immediately. Filenames are human-readable, for example `Movie Name.en.srt` or `Track Title.es.vtt`.
4. **Translate if wanted.** Leave **Recommended for this Mac** selected. Context is used for reference, gender, idioms, phraseology, metaphors and continuity across subtitle fragments.
5. **Generate voice if wanted.** Kokoro speaks dialogue only. Cues such as `[MUSIC]`, `[LAUGHTER]` and `[APPLAUSE]` remain in subtitle files but are removed from the temporary TTS input.
6. **Export dubbed media.** M5 timing-fits long lines, ducks the original primary soundtrack under speech, then remuxes the result.

## Subtitle filenames

Internal work files remain in DubLocal's temporary cache, but files exposed to the user use the loaded media name plus language suffix:

```text
Movie Name.en.srt
Movie Name.es.vtt
Track Title.ru.srt
```

Translated SRTs use the target-language suffix. Changing SRT/VTT/TXT does not rerun transcription.

## Translation: Recommended for this Mac

DubLocal does not force the biggest model onto every machine.

| Mac class | Default contextual profile |
| --- | --- |
| Apple Silicon below 12 GB | Qwen3 4B · single pass · 8k input cap |
| Apple Silicon 12–23 GB | Qwen3 8B · single pass · 16k input cap |
| Apple Silicon 24 GB+ | Qwen3 8B · senior review pass · up to 24k input context |
| Intel below 24 GB | Qwen3 4B · smaller context |
| Intel 24 GB+ | Qwen3 8B · single pass · reduced context |

The actual llama.cpp context/KV allocation is reduced with the profile as well. An 8 GB M1 is therefore not given a small prompt while still reserving a full 32k runtime context.

Main shows only **Recommended for this Mac · Lightweight / Balanced / Best quality**. The detailed reason, model and context allocation live in the collapsed engine details and Model Manager.

Contextual translation uses:

- nearby dialogue;
- sampled programme-wide context that grows with programme length;
- recent approved translations as terminology/style memory;
- discourse-aware gender/reference handling;
- idiom/phraseologism translation by meaning and register rather than word-for-word substitution;
- metaphor preservation without inventing new imagery;
- on the Best-quality profile, a second senior review pass.

DubLocal also validates IDs, timestamps, runtime leakage and wrong-script contamination before writing a translated SRT.

Automatic captions are not ground truth. If the Original column is already wrong, use local Whisper—especially **Accurate · Large v3 Turbo Q5** for songs, accents and difficult audio—before judging the translator.

## Caption cues are subtitles, not speech

Closed-caption cues remain visible in SRT/VTT because they are useful to viewers:

```text
[MUSIC]
[APPLAUSE]
[LAUGHTER]
```

They are not sent to the translator as dialogue and are not spoken by Kokoro. Inline cues are also stripped only from the temporary TTS input, so `[LAUGHS] Hello` becomes spoken `Hello` while the subtitle remains unchanged.

## M5: dubbed-media export

M5 deliberately separates audio processing from video encoding.

### Replace primary audio — default

DubLocal creates a new mixed soundtrack. The original primary soundtrack is ducked while generated speech is present, then mixed with the voice track. Additional original audio tracks are preserved where possible. The DubLocal mix becomes the default audio track.

This is **ducking + overlay**, not true dialogue/background source separation. Original dialogue may remain quietly audible under the dub. Source separation is a future feature.

### Add dubbed audio as second track

All original audio tracks remain untouched and a DubLocal mixed track is appended as another selectable audio stream. It receives language/title metadata and is not forced to default.

### Video is normally copied, not re-encoded

M5 uses FFmpeg stream-copy for video (`-c:v copy`) whenever the requested container can carry the original video stream. This is fast and avoids generation loss.

**MKV is recommended** because it preserves mixed codec/track combinations most reliably. MP4 is available when compatible. If MP4 cannot accept the source streams by remuxing, DubLocal tells you to use MKV rather than silently spending hours re-encoding video.

### Timing fitting

M5 never truncates spoken words. For a voice segment that runs past its subtitle window it:

1. borrows real silence before the next spoken segment when available;
2. if still needed, applies modest tempo increase up to 1.25×;
3. reports any line that still cannot fit safely.

This is the first timing engine; semantic shortening/rephrasing can be added later without changing the media-export architecture.

### M5 filenames

Dubbed media uses predictable names such as:

```text
Movie Name.dub.es.mkv
Track Title.dub.en-US.mp4
```

## Settings

**Updates** — Check → Install → Restart. **Repair installation** can restore official tracked files after saving a patch backup while preserving models/caches/jobs.

**Model Manager** — Whisper, hardware-aware contextual translation, legacy OPUS and Kokoro. Heavy models download only on request.

**Local Resources** — reports reusable FFmpeg/ffprobe, whisper.cpp, llama.cpp, shared Hugging Face cache and compatible isolated Python runtimes.

## Reuse first, install second

DubLocal reuses system executables and shared Hugging Face model assets when safe. It never merges another application's Python environment into its own; compatible Python backends are invoked as isolated worker processes.

## Temporary files

Temporary YouTube media, transcription WAVs, working subtitles, llama-server logs, TTS segments, fitted voice audio, dubbed mixes and remux outputs live under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes jobs older than 24 hours and caps this temporary cache at 4 GiB by pruning the oldest jobs first. Persistent model assets and the shared Hugging Face cache are not treated as temporary.

## Kokoro coverage

Official Kokoro language frontends currently exposed include American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese. Translation can support languages that Kokoro cannot voice; DubLocal does not silently use the wrong pronunciation frontend.

## Install on macOS

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates `~/Applications/DubLocal.app` and `~/Applications/Stop DubLocal.app`. After installation, normal updates happen inside DubLocal.

## Documentation

- [Changelog](CHANGELOG.md)
- [User guide](docs/USER_GUIDE.md)
- [Installation](docs/INSTALLATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Quality notes](docs/QUALITY_NOTES.md)
- [UX notes](docs/UX_NOTES.md)
- [Third-party licences](THIRD_PARTY_LICENSES.md)
- [Model registry](MODEL_LICENSES.json)

## Roadmap

```text
M1   Source + existing captions                           ✅
M2   Local transcription / Whisper                        ✅
M3   Local subtitle translation                          ✅
M4   Kokoro local voice generation                       ✅
M5   Timing + soundtrack mix + stream-copy export         ✅ current
M6   Rich media preview / advanced timing                 planned
M7   Signed/notarized Mac packaging                       planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json`.
