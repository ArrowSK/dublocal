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
  └─ local transcription fallback
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

1. The Gradio layer may orchestrate jobs but must not contain media-processing logic.
2. Media input backends return a small serializable source description used by the UI state.
3. Models are optional. The base application must launch without transcription, translation, or TTS models installed.
4. Every model or binary intended for redistribution must be explicitly allowed by the licence registry before release packaging.
5. YouTube media/caption access remains separate from local-file processing and never implements DRM or access-control circumvention.
6. Intermediate outputs should be cached per job so future segment-level editing does not require regenerating an entire movie.
7. A failed optional backend must not make the basic subtitle workflow unusable.

## Milestone 1

Implemented:

- local media inspection via `ffprobe`;
- local text-subtitle stream discovery;
- local subtitle extraction via `ffmpeg`;
- YouTube metadata and caption discovery via the Python `yt-dlp` package;
- YouTube caption extraction without downloading video/audio;
- rights-confirmation gate before extraction;
- simple Matrix-inspired Gradio shell;
- unit tests for the media foundation.

Deliberately not implemented yet:

- OCR for image-based subtitles;
- speech-to-text transcription;
- translation;
- Kokoro TTS;
- dialogue/background separation;
- voice timing and audio ducking;
- rendered dubbed video;
- signed/notarized macOS application packaging.

## Planned internal segment model

The next stage should normalize every subtitle/transcription source to records equivalent to:

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

Translation and TTS should operate on this model rather than directly on SRT/VTT files.
