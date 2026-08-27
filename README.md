<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, contextual translation, AI voice-over and track-aware media export for macOS.<br>
  Processing stays on your Mac.
</p>

<p align="center">
  <strong>Current development build: v0.5.3.dev0 · M5 Stabilization</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal turns a YouTube link or local media file into a reusable timed subtitle timeline. You can stop with subtitles, translate them locally, generate a Kokoro voice track, package subtitles into the original media, or continue to a dubbed MKV/MP4.

The normal interface stays deliberately small:

**Main:** Source → Subtitles → Translate → Voice-over → Export  
**Settings:** Updates · Model Manager · Local Resources

There is no packaged DMG/GitHub Release yet. Development builds update from official `main` inside DubLocal.

## What works now

| Stage | What DubLocal does |
| --- | --- |
| Source | YouTube URL or local video/audio; ffprobe/yt-dlp inspection |
| Subtitles | Existing text captions or local `whisper.cpp`; SRT/VTT/TXT download |
| Translation | Hardware-aware Qwen3 4B/8B contextual translation; optional legacy OPUS |
| Voice | Kokoro; caption cues stay silent; automatic lower/higher vocal-range matching |
| Timing | Per-line timing fit against subtitle start/end windows |
| Mixing | Stable reduced original bed + stronger dialogue/singing-window suppression |
| Export | Replace/add dub audio, subtitle-only package, selectable subtitle streams, video stream-copy by default |

## Normal workflow

1. **Load source.** The Source card confirms title, duration and available tracks.
2. **Get subtitles.** Use a text caption track or **Transcribe locally**. The result is immediately downloadable; translation is optional.
3. **Translate if wanted.** Leave **Recommended for this Mac** selected. `From = Auto` resolves the detected/identified subtitle language automatically for contextual translation.
4. **Generate voice if wanted.** **Auto · match original vocal range** is the normal choice. DubLocal can switch between lower/higher Kokoro presets per segment without loading a second TTS model.
5. **Export.** Choose a dubbed mix or **Package original + subtitles · no dub**.

## v0.5.3: transcription without reopening the ghost problem

Whisper can either invent speech or miss difficult words. DubLocal deliberately does not solve one problem by globally making the decoder more eager.

The reliability path is layered:

- ordinary speech can use the tiny official whisper.cpp Silero VAD helper when supported;
- the Accurate music profile avoids rolling text context that can create self-reinforcing lyric loops;
- severe near-duplicate repetition storms are re-decoded in isolation and suppressed if they remain untrustworthy;
- v0.5.3 selectively rechecks only suspicious sparse lines and short internal gaps;
- a missing-word recovery is accepted only when **two isolated no-context passes agree closely**;
- candidates that merely echo neighbouring subtitles are rejected.

For Apple Silicon below 12 GiB, extra recovery is capped at **3 regions / 24 seconds** per job. This is not a hidden second full-video transcription pass.

For songs, accents and difficult audio, **Accurate · Large v3 Turbo Q5 · 547 MiB** is the stronger local choice.

## Translation: Recommended for this Mac

DubLocal scales the model and llama.cpp context allocation to the hardware:

| Mac class | Default profile |
| --- | --- |
| Apple Silicon <12 GB | Qwen3 4B · single pass · 8k input cap |
| Apple Silicon 12–23 GB | Qwen3 8B · single pass · 16k input cap |
| Apple Silicon 24 GB+ | Qwen3 8B · senior review · up to 24k |
| Intel <24 GB | Qwen3 4B · smaller context |
| Intel 24 GB+ | Qwen3 8B · single pass · reduced context |

The contextual prompt uses nearby dialogue, programme context and prior accepted translations. It explicitly handles reference/gender where supported by context, idioms/phraseology by meaning and register, metaphors, recurring terminology, slang and profanity. Subtitle IDs/timestamps and output script are validated before an SRT is written.

Standalone tags such as `[MUSIC]` are structural subtitle data: they stay unchanged and are not translated as dialogue.

## Voice-over

Caption cues remain useful in SRT/VTT but are never speech instructions. A temporary TTS timeline removes them before Kokoro:

```text
[MUSIC]          → silence
[LAUGHS] Hello   → speaks “Hello”
```

Automatic voice matching is an acoustic lower/higher-range heuristic, not speaker identification or gender-identity classification. It reuses one Kokoro pipeline and changes voice presets per segment.

## v0.5.3 timing and loudness

### Timing

Each generated line targets its own subtitle window. DubLocal measures the actual WAV duration and changes tempo locally. v0.5.3 chains legal FFmpeg `atempo` stages for an effective **0.30×–2.50×** correction range and can perform a small second correction when rounding leaves the spoken end more than roughly 25 ms from the target.

Subtitle timestamps themselves are never moved by this process. Truly pathological stretches are still reported rather than forced.

### Soundtrack balance

Consumer media usually provides a married soundtrack rather than a dialogue-free Music & Effects stem. DubLocal therefore does not claim perfect vocal removal.

The original soundtrack now stays at a **stable reduced bed level** throughout a dubbed mix instead of becoming dramatically louder between DubLocal lines. Source subtitle dialogue/singing windows are attenuated further, while gentle compression and limiting keep the combined programme level controlled.

This is lightweight DSP, not source separation, and is intentionally suitable for M1-class hardware.

## Export modes

**Replace primary audio — default**  
Creates a DubLocal mix and makes it the default audio stream; additional original tracks are retained where possible.

**Add dubbed audio as second track**  
Keeps original audio streams untouched and appends the DubLocal mix as another selectable track.

**Package original + subtitles · no dub**  
Keeps original audio untouched, adds the current source/transcribed subtitle as a selectable stream, and adds neither translated subtitles nor DubLocal audio.

When a normal dubbed export has both generated source and translated SRTs, both are embedded as selectable subtitle tracks by default. Nothing is burned into the picture.

## Video quality and recoding

**Original / best available** is the default.

For YouTube, 2160p / 1440p / 1080p / 720p / 480p acts as a source-quality ceiling before download; final video is then stream-copied.

For local files, **Original** uses `-c:v copy`. Selecting a lower resolution is an explicit opt-in to Apple VideoToolbox H.264 encoding. DubLocal does not silently re-encode a local video merely because audio/subtitles changed.

**MKV is recommended** for multi-track output. MP4 is available for compatible stream combinations.

## User-facing filenames

```text
Movie Name.en.srt
Movie Name.es.vtt
Movie Name.dub.es.mkv
```

Internal work files remain disposable cache artifacts rather than cluttering normal folders.

## Temporary files

Generated/intermediate jobs live under:

```text
~/Library/Caches/DubLocal/jobs/
```

Normal launch removes jobs older than 24 hours and caps this cache at 4 GiB, pruning oldest jobs first. Persistent Whisper/Qwen/Kokoro assets and the shared Hugging Face cache are excluded.

## Install

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates `~/Applications/DubLocal.app` and `~/Applications/Stop DubLocal.app`. After that, ordinary updates happen under **Settings → Updates**.

## Documentation

- [Changelog](CHANGELOG.md)
- [User guide](docs/USER_GUIDE.md)
- [Installation](docs/INSTALLATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [M5.3 stabilization notes](docs/M5_3_STABILIZATION.md)
- [Quality notes](docs/QUALITY_NOTES.md)
- [UX principles](docs/UX_NOTES.md)
- [Third-party licences](THIRD_PARTY_LICENSES.md)
- [Model registry](MODEL_LICENSES.json)

## Roadmap

```text
M1   Source + existing captions                           ✅
M2   Local transcription / Whisper                        ✅
M3   Local subtitle translation                           ✅
M4   Kokoro local voice generation                        ✅
M5   Timing + soundtrack mix + track-aware export         ✅ current
M6   Rich preview / optional source separation            planned
M7   Signed/notarized Mac packaging                       planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json`.
