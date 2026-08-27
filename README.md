<p align="center">
  <img src="assets/macos/DubLocal.svg" alt="DubLocal logo" width="132">
</p>

<h1 align="center">DubLocal_</h1>

<p align="center">
  Local subtitles, context-aware translation and AI voice-over tooling for macOS.<br>
  Your local media stays on your Mac.
</p>

<p align="center">
  <strong>Current development build: v0.4.2.dev0 · Subtitle Export + Translation Quality Pass</strong><br>
  macOS 13+ · Apple Silicon and Intel · Apache-2.0
</p>

---

DubLocal turns a YouTube link or a local video/audio file into a reusable timed subtitle timeline. You can stop there and download subtitles, translate them locally, or continue into local synthetic voice generation.

The normal interface deliberately separates work from maintenance:

- **Main** — Source → Subtitles → Translate → Voice-over.
- **Settings** — Updates, Model Manager and Local Resources.

There is currently **no packaged GitHub Release**. `v0.4.2.dev0` is the current development build once this quality pass reaches `main`.

## What works now

| Stage | Status | What DubLocal does |
| --- | --- | --- |
| Media input | ✅ | YouTube URL or local video/audio |
| Existing subtitles | ✅ | Finds and extracts supported caption/subtitle tracks |
| Local transcription | ✅ | Timestamped subtitles through `whisper.cpp` |
| Subtitle download | ✅ v0.4.2 | Download SRT by default, or VTT/TXT, without translating |
| Best local translation | ✅ v0.4.2 | Qwen3 8B + context + senior review through `llama.cpp` |
| Fast legacy translation | ✅ | OPUS sentence-level translation remains optional |
| AI voice | ✅ M4 | Kokoro voice-only WAV from source or translated SRT |
| Timing / soundtrack mix | Next | Fit speech and duck/mix original audio |
| Media export | Planned | Stream-copy video where possible; replace/add dubbed audio |

## Subtitles are a complete output, not merely a translation input

After **Use existing subtitles** or **Transcribe locally**, DubLocal immediately exposes a downloadable subtitle file in **2 · Subtitles**.

Choose the output format before or after transcription:

- **SRT** — default and the normal choice for video players/editors;
- **WebVTT** — useful for web video;
- **TXT** — plain transcript without timestamps.

Changing the download format converts the existing timeline. It does not rerun Whisper.

## Source quality matters

Translation cannot reliably reconstruct words that were already misheard by an automatic captioner. DubLocal therefore distinguishes the source of the subtitle timeline.

If a selected track is **YouTube automatic captions**, the UI warns that recognition errors may propagate into translation. For songs, strong accents, difficult dialogue or noisy audio, the optional local **Accurate · Large v3 Turbo Q5** Whisper model is the stronger transcription choice.

This distinction is intentional: bad source transcription and bad translation are different failures and should not be hidden behind one “AI quality” label.

## Best-quality translation in v0.4.2

Real-language testing showed that the previous Qwen3 4B development backend could still produce literal grammar, poor word choices and occasional mixed-script output. It is no longer the recommended translator.

**Best quality · Qwen3 8B + review** is the v0.4.2 default quality path.

It uses:

1. nearby source dialogue before and after the current lines;
2. programme-wide sampled source context;
3. recent approved translations as terminology/style memory;
4. explicit target-language grammar/idiom guidance;
5. a second **senior review pass** using the same source and context.

The context budget grows automatically with media duration, from roughly 4k input tokens for short material up to 24,576 input tokens within the model's native 32k context.

For short media, DubLocal deliberately uses larger chunks. A short song can normally be translated in one contextual chunk rather than repeatedly starting small independent requests.

## Quality model and local runtime

The recommended backend is the official **Qwen3 8B GGUF Q4_K_M** model through `llama.cpp`.

- weight size: about **5.03 GB**;
- licence: **Apache-2.0**;
- download: only when the user clicks **Prepare / verify contextual translation**;
- storage: normal shared Hugging Face cache;
- integrity: immutable model revision + SHA-256 verification;
- runtime: existing compatible `llama.cpp` is reused first;
- execution: one loopback-only `llama-server` session is preferred for the entire translation job, so the model is loaded once rather than once per subtitle chunk.

The previous Qwen3 4B development model is retained in `MODEL_LICENSES.json` only for provenance. v0.4.2 does not select or download it.

Users who prioritise storage/speed can still explicitly select **Fast legacy · OPUS**. DubLocal never silently downgrades Best quality to OPUS or sends translation to a cloud service.

## Subtitle integrity rules

Translation output must prove that it is safe to write before DubLocal creates the translated SRT.

- Subtitle IDs, order and timestamps are preserved.
- Standalone cues such as `[MUSIC]`, `[APPLAUSE]` and `[LAUGHTER]` are copied exactly and never translated.
- llama.cpp banners, model paths, prompt text and runtime logs are rejected.
- Unexpected CJK/Hangul characters are rejected for the current European target-language set.
- Cyrillic targets reject substantial untranslated Latin-script leakage; Latin targets reject substantial Cyrillic leakage.
- Missing IDs can be recovered while retaining full contextual information.
- If alignment or output language still cannot be validated, DubLocal stops rather than writing a corrupted subtitle file.

These checks catch structural contamination. They do not pretend that software can prove literary quality automatically, which is why v0.4.2 also adds the stronger model and review pass.

## Normal workflow

1. Open **DubLocal.app**.
2. Choose **YouTube** or **Local file**, then **Load source**.
3. Under **2 · Subtitles**, use an existing track or transcribe locally.
4. Download the SRT/VTT/TXT immediately if subtitles are all you need.
5. If translating, choose source and target language and leave **Best quality · Qwen3 8B + review** selected.
6. If the quality model is not installed, open **Settings → Model Manager → Contextual translation** and prepare it once.
7. Translate and review the side-by-side subtitle preview.
8. If the target language is supported by Kokoro, optionally generate a local voice-only track.

M5 will turn that voice track into practical dubbed-media output with duration fitting, soundtrack ducking/mixing and stream-copy video remuxing.

## Settings

**Settings → Updates**

Use **Check for updates → Install update → Restart DubLocal**. **Repair installation** restores official tracked application files and refreshes the managed environment while preserving models, caches, generated jobs and untracked user files.

**Settings → Model Manager**

- Whisper transcription models, from Tiny/Base through optional Accurate Large-v3-Turbo-Q5.
- Contextual translation: Qwen3 8B + `llama.cpp` — recommended quality path.
- Fast legacy translation: OPUS — optional lightweight path.
- Kokoro voice generation.

**Settings → Local Resources**

Shows reusable FFmpeg, ffprobe, whisper.cpp, llama.cpp, Hugging Face cache and compatible external Python environments.

## Reuse first, install second

DubLocal avoids duplicating large local components when reuse is safe.

System executables are reused from the Mac. Model assets use the normal shared Hugging Face cache. Python virtual environments remain isolated: DubLocal never injects another application's `site-packages` into its own interpreter; supported Python backends are reused through separate processes instead.

## Temporary files

Working files are not written into the repository or Documents folder. Temporary media, transcription audio, intermediate subtitles, llama-server logs and generated job assets live under the macOS DubLocal cache:

```text
~/Library/Caches/DubLocal/jobs/
```

On normal startup DubLocal removes jobs older than 24 hours and caps this temporary cache at 4 GiB by pruning the oldest jobs first. Persistent models and the shared Hugging Face cache are not part of that automatic cleanup.

## Kokoro coverage

Official Kokoro support currently exposed by DubLocal includes American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese and Mandarin Chinese.

Targets such as Hungarian, Russian and German can be translated as subtitles but are not voiced by the official Kokoro backend. Translation and TTS remain separate plugins by design.

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

After installation, normal use and updates happen inside DubLocal rather than Terminal.

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for details.

## Planned dubbed-media output

DubLocal will not re-encode video merely because a new soundtrack is created. Where compatible, FFmpeg will copy the original video stream and process/remux audio only.

M5 is planned to offer:

- **Replace primary audio — default:** make the DubLocal mixed soundtrack primary while preserving underlying music/effects through audio mixing/ducking.
- **Add dubbed audio as second track:** keep original audio intact and add DubLocal's dubbed mix as another selectable audio track.

MKV is the natural multi-track format; MP4 remains available when the selected streams/codecs are compatible.

## Documentation

- [Changelog](CHANGELOG.md)
- [User guide](docs/USER_GUIDE.md)
- [Installation](docs/INSTALLATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [UX notes](docs/UX_NOTES.md)
- [Third-party licences](THIRD_PARTY_LICENSES.md)
- [Model registry](MODEL_LICENSES.json)

## Roadmap

```text
M1   Source + existing captions                           ✅
M2   Local transcription / Whisper                        ✅ validated
M3   Local OPUS subtitle translation                      ✅ legacy path
M3.1 Context-aware translation foundation                 ✅
M4   Kokoro local voice generation                        ✅
v0.4.2 Subtitle export + 8B translation quality pass      current
M5   Voice timing + audio mix + stream-copy export        next
M6   Preview + final rendered/remuxed media                planned
M7   Signed/notarized Mac packaging                       planned
```

## Legal note

DubLocal is a media-processing tool, not a licence to copy media. Process only content you have the right or legal authority to download, translate, modify or redistribute. DubLocal does not implement DRM or access-control circumvention.

## Licence

DubLocal itself is Apache-2.0. Third-party software and model weights keep their own licences. See `THIRD_PARTY_LICENSES.md` and `MODEL_LICENSES.json`.
