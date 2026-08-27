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

DubLocal turns a YouTube link or a local video/audio file into a reusable timed subtitle timeline, translates it locally when wanted, and can generate a local synthetic voice track. Cloud transcription, translation and TTS are not required.

The application is intentionally split into two places:

- **Main** is where you process media.
- **Settings** is where you update/repair DubLocal and manage optional local models.

There is currently **no packaged GitHub Release**. `v0.4.1.dev0` is the current development build on `main`.

## What works now

| Stage | Status | What DubLocal does |
| --- | --- | --- |
| Media input | ✅ | YouTube URL or local video/audio |
| Existing subtitles | ✅ | Finds and extracts supported caption/subtitle tracks |
| Missing captions | ✅ | Creates timestamped subtitles locally with `whisper.cpp` |
| Subtitle export | ✅ | Download immediately as SRT (default), WebVTT, TXT or CSV; translation is optional |
| Contextual translation | ✅ M3.1 | Qwen3 4B through one local `llama-server` session; context grows with programme length |
| Fast legacy translation | ✅ | OPUS sentence-level translation remains optional |
| AI voice | ✅ M4 | Kokoro voice-only WAV from source or translated SRT |
| Timing / soundtrack mix | Next | Fit speech and duck/mix original audio |
| Media export | Planned | Stream-copy video where possible; replace/add dubbed audio |

## Why translation changed in v0.4.1

The original OPUS translator was small and fast, but it treated subtitle entries as independent sentences. That is not good enough for film, interviews or long-form dialogue: pronouns, names, slang, jokes and tone often depend on surrounding material.

**Contextual quality** is therefore now the default.

DubLocal supplies three context layers:

1. nearby source dialogue before and after the target lines;
2. programme-wide sampled source dialogue so recurring names/topics remain visible;
3. recent translated lines as rolling terminology/style memory.

The context budget grows automatically with media duration. Short material starts at about **4k input tokens**; longer programmes progressively receive more context, up to **24,576 input tokens** inside Qwen3's native 32k context. Timestamps and subtitle IDs are preserved exactly.

A translation job now loads Qwen once into a local `llama-server`, reuses that same model process for every chunk/recovery request, and shuts it down at the end. Short material is packed into fewer chunks when it safely fits, which removes the previous repeated-model-load overhead.

Translation output uses a strict DubLocal marker + subtitle-ID protocol over llama.cpp's local OpenAI-compatible HTTP API. Runtime banners, terminal control characters and echoed prompts are never accepted as subtitle text.

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
2. On **Main**, choose **YouTube** or **Local file** and click **Load source**.
3. Use existing subtitles or run **Transcribe locally** with Whisper.
4. Download that source timeline immediately if that is all you need. **SRT** is the default; **WebVTT**, **TXT** and **CSV** are optional exports and do not rerun transcription.
5. If translation is wanted, choose source and target language. Leave **Contextual quality** selected for normal use.
6. If the quality model is not ready, go to **Settings → Model Manager → Contextual translation** and click **Prepare / verify contextual translation** once.
7. Translate and review the side-by-side preview.
8. If the target language is supported by Kokoro, generate a local voice-only track.

M5 will turn that voice track into a practical dubbed-media output with duration fitting, soundtrack ducking/mixing and stream-copy video remuxing.

## About songs and difficult audio

Translation quality depends on the source transcript. Song lyrics, backing vocals, stylized pronunciation and noisy mixes are much harder for speech recognition than ordinary dialogue. If the **Original** column is already wrong, use a more accurate Whisper model such as **Small** before evaluating the translator. Context should help resolve ambiguity; it should not invent words that were never transcribed correctly.

## Settings

**Settings → Updates**

Use **Check for updates → Install update → Restart DubLocal**. **Repair installation** is available when tracked program files or the managed environment need to be restored. Repair preserves models, caches, generated jobs and untracked user files.

**Settings → Model Manager**

- Whisper models for transcription.
- Contextual translation: Qwen3 4B + `llama.cpp` — recommended.
- Fast legacy translation: OPUS — optional.
- Kokoro voice generation.

**Settings → Local Resources**

Shows reusable FFmpeg, ffprobe, whisper.cpp, `llama-cli`, `llama-server`, Hugging Face cache and compatible external Python environments such as Kokoro runtimes.

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
M3.1 Context-aware Qwen3 translation                      ✅ implementation; local quality validation ongoing
M4   Kokoro local voice generation                        ✅ implementation
M5   Voice timing + audio mix + stream-copy export        next
M6   Preview + final rendered/remuxed media                planned
M7   Signed/notarized Mac packaging                       planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json`.
