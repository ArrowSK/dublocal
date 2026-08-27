<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, context-aware translation and AI voice-over tooling for macOS.<br>
  Your local media stays on your Mac.
</p>

<p align="center">
  <strong>Current development build: v0.4.1.dev0 · M4 + M3.1</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal turns a YouTube link or a local video/audio file into a reusable timed subtitle timeline, translates it locally, and can generate a local synthetic voice track. Cloud transcription, translation and TTS are not required.

The application is intentionally split into two places:

- **Main** is where you process media.
- **Settings** is where you update/repair DubLocal and manage optional local models.

There is currently **no packaged GitHub Release**. `v0.4.1.dev0` is the current development build on `main` once M3.1 is merged.

## What works now

| Stage | Status | What DubLocal does |
| --- | --- | --- |
| Media input | ✅ | YouTube URL or local video/audio |
| Existing subtitles | ✅ | Finds and extracts supported caption/subtitle tracks |
| Missing captions | ✅ | Creates timestamped subtitles locally with `whisper.cpp` |
| Contextual translation | ✅ M3.1 | Qwen3 4B through `llama.cpp`; context grows with programme length |
| Fast legacy translation | ✅ | OPUS sentence-level translation remains optional |
| AI voice | ✅ M4 | Kokoro voice-only WAV from source or translated SRT |
| Timing / soundtrack mix | Next | Fit speech and duck/mix original audio |
| Media export | Planned | Stream-copy video where possible; replace/add dubbed audio |

## Why translation changed in v0.4.1

The original OPUS translator was small and fast, but it treated subtitle entries as independent sentences. That is not good enough for film, interviews or long-form dialogue: pronouns, names, slang, jokes and tone often depend on what was said before and what is coming next.

**Contextual quality** is therefore now the default.

DubLocal translates small groups of target subtitle lines while supplying three context layers:

1. nearby source dialogue before and after the target lines;
2. programme-wide sampled source dialogue so recurring names/topics remain visible;
3. recent translated lines as rolling terminology/style memory.

The context budget grows automatically with media duration. Short material starts at about **4k input tokens**; longer programmes progressively receive more context, up to **24,576 input tokens** inside Qwen3's native 32k context. Timestamps and subtitle IDs are preserved exactly.

For users who prefer speed/storage over quality, **Fast legacy · OPUS** remains available explicitly. DubLocal never silently falls back from contextual translation to OPUS or to a cloud service.

## Local quality model

The current contextual backend is the official **Qwen3 4B GGUF Q4_K_M** model, run with `llama.cpp`.

- model size: about **2.5 GB**;
- model licence: Apache-2.0;
- runtime: `llama.cpp` (MIT);
- model is downloaded only when you click **Prepare / verify contextual translation**;
- the normal shared Hugging Face cache is reused;
- an existing `llama.cpp` installation is reused before DubLocal installs another runtime;
- the downloaded GGUF is pinned to an immutable revision and SHA-256 verified.

See `MODEL_LICENSES.json` for the exact revision/hash.

## Normal workflow

1. Open **DubLocal.app**.
2. On **Main**, choose **YouTube** or **Local file** and scan it.
3. Extract existing subtitles or run **Local transcription · Whisper**.
4. Under **Local translation**, choose source and target language. Leave **Contextual quality** selected for normal use.
5. If the quality model is not ready, go to **Settings → Model Manager → Contextual translation** and click **Prepare / verify contextual translation** once.
6. Translate and review the side-by-side preview.
7. If the target language is supported by Kokoro, generate a local voice-only track.

M5 will turn that voice track into a practical dubbed-media output with duration fitting, soundtrack ducking/mixing and stream-copy video remuxing.

## Settings

**Settings → Updates**

Use **Check for updates → Install update → Restart DubLocal**. **Repair installation** is available when tracked program files or the managed environment need to be restored. Repair preserves models, caches, generated jobs and untracked user files.

**Settings → Model Manager**

- Whisper models for transcription.
- Contextual translation: Qwen3 4B + `llama.cpp` — recommended.
- Fast legacy translation: OPUS — optional.
- Kokoro voice generation.

**Settings → Local Resources**

Shows reusable FFmpeg, ffprobe, whisper.cpp, `llama.cpp`, Hugging Face cache and compatible external Python environments such as Kokoro runtimes.

## Reuse first, install second

DubLocal avoids duplicating large local components when reuse is safe.

System executables are reused from the Mac. Shared model assets use the normal Hugging Face cache. Python virtual environments remain isolated: DubLocal does not inject another application's `site-packages` into its own interpreter; supported Python backends run through a narrow separate-process bridge instead.

## Kokoro coverage

Official Kokoro support currently exposed by DubLocal includes American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Targets such as Hungarian, Russian and German can be translated as subtitles but are not voiced by official Kokoro. Translation and TTS are deliberately separate backends.

## Install on macOS

```bash
git clone https://github.com/ArrowSK/dublocal.git
cd dublocal
zsh scripts/macos/install-launcher.sh
```

The installer creates:

```text
~/Applications/DubLocal.app
~/Applications/Stop DubLocal.app
```

After installation, ordinary use and updates happen inside DubLocal rather than Terminal.

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for details.

## Planned dubbed-media output

DubLocal will not re-encode video merely because a new soundtrack is created. Where compatible, FFmpeg will copy the original video stream and process/remux audio only.

M5 will offer:

- **Replace primary audio — default:** make the DubLocal mixed soundtrack primary while preserving underlying music/effects through audio mixing/ducking.
- **Add dubbed audio as second track:** keep original audio intact and add DubLocal's dubbed mix as another selectable track.

MKV is the natural multi-track format; MP4 remains available when the source streams/codecs are compatible.

## Documentation

- [Changelog](CHANGELOG.md)
- [User guide](docs/USER_GUIDE.md)
- [Installation](docs/INSTALLATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Third-party licences](THIRD_PARTY_LICENSES.md)
- [Model registry](MODEL_LICENSES.json)

## Roadmap

```text
M1   Source + existing captions                           ✅
M2   Local transcription / Whisper                        ✅ validated
M3   Local OPUS subtitle translation                      ✅ legacy path
M3.1 Context-aware Qwen3 translation                      ✅ implementation; local validation pending
M4   Kokoro local voice generation                        ✅ implementation
M5   Voice timing + audio mix + stream-copy export        next
M6   Preview + final rendered/remuxed media                planned
M7   Signed/notarized Mac packaging                       planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json`.
