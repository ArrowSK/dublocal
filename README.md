<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, contextual translation, AI voice-over and dubbed-media export for macOS.<br>
  Your processing stays on your Mac.
</p>

<p align="center">
  <strong>Current development build: v0.5.1.dev0 · Voice Match + Export Refinement</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal turns a YouTube link or local media file into a timed subtitle timeline. You can stop with subtitles, translate them locally, generate a local voice track, or continue through Export to a dubbed MKV/MP4 without needlessly re-encoding the video.

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
| AI voice | ✅ | Kokoro voice-only track; caption cues stay silent; automatic original-vocal-range matching |
| Timing fit | ✅ | Borrow silence, then modestly speed overflowing speech |
| Soundtrack mix | ✅ | Strong subtitle-window suppression of original dialogue/singing under the dub |
| Subtitle muxing | ✅ | Original + translated generated subtitles embedded as selectable tracks |
| Media export | ✅ | Replace/add dubbed audio; YouTube quality selection; local stream-copy by default |

## The normal workflow

1. **Load source.** Choose YouTube or Local file and click **Load source**. The Source card confirms what is loaded.
2. **Get subtitles.** Use an existing track or transcribe locally. DubLocal carries the detected subtitle language forward automatically when Whisper/track metadata provides it.
3. **Stop here if you only need subtitles.** The file is downloadable immediately. Filenames are human-readable, for example `Movie Name.en.srt` or `Track Title.es.vtt`.
4. **Translate if wanted.** Leave **Recommended for this Mac** selected. Context is used for reference, gender, idioms, phraseology, metaphors and continuity across subtitle fragments.
5. **Generate voice if wanted.** The normal voice choice is **Auto · match original vocal range**. DubLocal performs a lightweight local acoustic pass and can use contrasting lower/higher Kokoro voices segment-by-segment when the original alternates. Manual voice selection remains available. Cues such as `[MUSIC]`, `[LAUGHTER]` and `[APPLAUSE]` remain in subtitle files but are removed from temporary TTS input.
6. **Export dubbed media.** DubLocal timing-fits long lines, strongly suppresses the original dialogue/singing across the source subtitle windows, mixes the translated voice, embeds generated original/translated subtitles, and remuxes the result.

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

Contextual translation uses nearby dialogue, sampled programme-wide context, recent accepted translations as terminology/style memory, discourse-aware gender/reference handling, idiom/phraseologism translation by meaning/register, metaphor preservation without invented imagery, and an optional senior review pass on the Best-quality profile.

DubLocal validates IDs, timestamps, runtime leakage and wrong-script contamination before writing a translated SRT.

Automatic captions are not ground truth. If the Original column is already wrong, use local Whisper—especially **Accurate · Large v3 Turbo Q5** for songs, accents and difficult audio—before judging the translator.

## Automatic voice matching

The automatic voice option is deliberately lightweight. It decodes the original primary audio to a low-rate local analysis stream, estimates the dominant vocal fundamental inside each subtitle window, and maps lower/higher vocal ranges to available Kokoro voice presets for the selected language.

This does **not** identify a person or infer gender identity. It is an acoustic preset-selection heuristic intended to avoid obvious lower/higher voice mismatches. If a subtitle line contains overlapping speakers, that line still receives one TTS voice. Languages that expose only one Kokoro voice simply use that voice.

The same Kokoro model/pipeline stays loaded while segment voice presets change, so automatic two-voice material does not require a second TTS model in memory.

## Caption cues are subtitles, not speech

Closed-caption cues remain visible in SRT/VTT because they are useful to viewers:

```text
[MUSIC]
[APPLAUSE]
[LAUGHTER]
```

They are not sent to the translator as dialogue and are not spoken by Kokoro. Inline cues are stripped only from the temporary TTS input, so `[LAUGHS] Hello` becomes spoken `Hello` while the subtitle remains unchanged.

## Dubbed-media export

Professional dubbing normally works from a dialogue-free Music & Effects stem. Consumer YouTube/local files normally contain a married mix, so DubLocal cannot remove only the original human voice without source separation.

v0.5.1 therefore uses the source subtitle timeline as the suppression guide. Original audio stays strongly ducked across each complete source dialogue/singing window—even when translated TTS is shorter—rather than jumping back to full volume as soon as generated speech stops. Closely spaced windows are merged to reduce pumping.

This remains **ducking + overlay**, not true dialogue/music/effects separation.

**Replace primary audio — default:** DubLocal creates a new mixed soundtrack and makes it the default audio track. Additional original audio tracks are preserved where possible.

**Add dubbed audio as second track:** all original audio tracks remain untouched and the DubLocal mixed track is appended as another selectable stream with language/title metadata.

### Original + translated subtitles are packaged, not burned

When generated source and translated SRTs are available, both are embedded as selectable subtitle streams. VLC and similar players can turn them on/off independently. No subtitle is burned into the image.

MKV can preserve existing source subtitle streams. MP4 packages the generated SRT tracks as `mov_text`; this changes the subtitle stream format only, not the video.

### Video quality

**Original / best available** is the default.

For YouTube, selecting 2160p / 1440p / 1080p / 720p / 480p chooses the best available source at or below that height before download. The selected video is then stream-copied during remux.

For local files, **Original** keeps the video bit-for-bit with `-c:v copy`. Selecting a lower resolution is an explicit request to re-encode that local video with Apple's H.264 VideoToolbox encoder. DubLocal does not upscale a lower-resolution local source merely because a higher option was selected.

**MKV is recommended** because it preserves mixed codec/track combinations most reliably. MP4 is available when compatible.

### Timing fitting

DubLocal never truncates spoken words. For a voice segment that runs past its subtitle window it borrows real silence before the next spoken segment, applies modest tempo increase up to 1.25× only if needed, and reports any line that still cannot fit safely.

Dubbed media uses predictable names such as:

```text
Movie Name.dub.es.mkv
Track Title.dub.en-US.mp4
```

## Settings

**Updates** — Check → Install → Restart. **Repair installation** can restore official tracked files after saving a patch backup while preserving models/caches/jobs.

**Model Manager** — Whisper, hardware-aware contextual translation, legacy OPUS and Kokoro. Heavy models download only on request.

**Local Resources** — reports reusable FFmpeg/ffprobe, whisper.cpp, llama.cpp, shared Hugging Face cache and compatible isolated Python runtimes.

## Temporary files

Temporary YouTube media, voice-analysis audio, transcription WAVs, working subtitles, llama-server logs, TTS segments, fitted voice audio, dubbed mixes and remux outputs live under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes jobs older than 24 hours and caps this temporary cache at 4 GiB by pruning the oldest jobs first. Persistent model assets and the shared Hugging Face cache are not treated as temporary.

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
M3   Local subtitle translation                           ✅
M4   Kokoro local voice generation                        ✅
M5   Timing + soundtrack mix + track-aware export         ✅ current
M6   Rich media preview / optional source separation      planned
M7   Signed/notarized Mac packaging                       planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json`.
