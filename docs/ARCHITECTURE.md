# DubLocal architecture

DubLocal is intentionally split into small replaceable backends so the UI never becomes coupled to one transcription, translation, TTS, or rendering implementation.

## Target pipeline

```text
Source
  ├─ YouTube
  └─ Local media
        ↓
Media inspection
        ↓
Subtitle acquisition
  ├─ embedded subtitle stream
  ├─ creator captions
  ├─ automatic captions
  └─ local whisper.cpp transcription fallback
        ↓
Normalized timed segment model
        ↓
Optional translation
        ↓
Optional TTS
        ↓
Timing / duration fitting
        ↓
Original-audio ducking + speech overlay
        ↓
Preview / export
```

## Design rules

1. The Gradio layer orchestrates jobs but does not implement media codecs or inference itself.
2. Media input backends return a small serializable source description used by the UI state.
3. Models are optional. The base application must launch without transcription, translation, or TTS models installed.
4. Every model or binary intended for redistribution must be explicitly allowed by the licence registry before release packaging.
5. YouTube media/caption access remains separate from local-file processing and never implements DRM or access-control circumvention.
6. Intermediate outputs are job-scoped so later segment editing can avoid regenerating unrelated work.
7. A failed optional backend must not make the basic existing-subtitle workflow unusable.
8. Expensive fallback work is explicit: DubLocal may recommend local transcription after a caption failure, but it does not silently download a model or start long inference without a user action.

## Milestone 1 foundation

Implemented:

- local media inspection via `ffprobe`;
- local text-subtitle stream discovery;
- local subtitle extraction via `ffmpeg`;
- YouTube metadata and caption discovery via the Python `yt-dlp` package;
- YouTube caption extraction without downloading video/audio;
- rights-confirmation gate;
- Matrix-inspired Gradio shell;
- branded macOS launcher.

## Milestone 2 transcription

Implemented:

- `src/dublocal/transcription.py` as the first transcription backend;
- external `whisper-cli` discovery, with Homebrew installation offered by the macOS installer;
- Apple Silicon normal whisper.cpp Metal path and Intel CPU compatibility mode;
- local FFmpeg conversion to 16-bit, 16 kHz, mono WAV before inference;
- audio-only YouTube acquisition when local transcription is explicitly requested;
- `tiny`, `base`, and `small` multilingual model allowlist;
- opt-in model installation/removal outside the repository;
- checksum verification against upstream published model hashes;
- source-language `auto` plus manual language codes;
- SRT output and timed UI preview;
- HTTP 429 caption failures routed to an explicit local-transcription fallback rather than treated as a dead end.

## Current normalized segment model

`src/dublocal/timeline.py` defines the current source timeline record:

```text
Segment
  index: int
  start_ms: int
  end_ms: int
  text: str
```

Integer milliseconds are used so subtitle timing can be round-tripped without floating-point drift. Both extracted SRT and Whisper-generated SRT can be normalized to this structure.

Translation and dubbing metadata should be layered around this stable source segment rather than mutating the timing representation. A future project-level record can add fields such as:

```json
{
  "id": "000123",
  "start_ms": 74220,
  "end_ms": 77840,
  "source_language": "en",
  "source_text": "Where are you going?",
  "target_language": "de",
  "target_text": null,
  "speaker": null,
  "tts_asset": null,
  "status": "source"
}
```

## Still deliberately out of scope

- OCR for image-based subtitles;
- translation;
- Kokoro TTS;
- dialogue/background separation;
- voice timing and audio ducking;
- rendered dubbed video;
- signed/notarized macOS application packaging.
