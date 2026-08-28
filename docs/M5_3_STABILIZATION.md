# M5.3 stabilization notes

**Current development build: v0.6.0.dev0**

This stabilization layer keeps the existing DubLocal workflow and public M5/M5.1 APIs. It addresses issues found in full end-to-end music-video tests without introducing a heavy source-separation dependency.

## Dubbed soundtrack balance

DubLocal keeps the original soundtrack at a reduced, stable bed level throughout the programme. During subtitle dialogue/singing windows the original mix is suppressed further, while the generated voice stays foreground. A gentle compressor and limiter bound the final mix so the level does not jump back to the full original soundtrack between dubbed lines.

This is intentionally lightweight DSP. Professional dubbing normally uses a dialogue-free M&E stem; consumer media usually does not provide one. DubLocal therefore uses dialogue-window ducking rather than pretending it can perfectly remove vocals from a mixed soundtrack.

The approach follows the same general principle as dialogue-anchored loudness workflows: foreground dialogue should remain intelligible and programme loudness range should be controlled, not merely peak-limited.

## Per-line timing

DubLocal now fits timing **during Kokoro generation**, not by broadly stretching the completed waveform afterward.

For each spoken subtitle line:

1. Kokoro generates a natural pilot version at the selected/default speed.
2. DubLocal measures the real generated duration against that subtitle's start/end window.
3. If the line is materially too short or too long, only that line is regenerated with a Kokoro-native speed chosen from the measured duration.
4. One additional native-generation correction is allowed when the first estimate is still meaningfully off.
5. Export uses the resulting synchronized voice track directly. It does not apply the old wide FFmpeg `atempo` timing stretch.

Kokoro-native timing stays in its normal 0.5×–2.0× range. If a translation cannot fit naturally even at that range, DubLocal reports the residual timing mismatch rather than creating obviously robotic speech. Subtitle timestamps themselves are not rewritten by TTS fitting.

This can cost extra inference time for individual lines that need regeneration, but the same Kokoro pipeline/model remains loaded inside the worker. It does not require a second model-sized memory allocation.

## Original media + subtitles only

The Export/Magic Flow path also supports original media with subtitles and no dub. This path:

- keeps the original audio untouched;
- does not add a DubLocal voice/dub track;
- can omit translation entirely;
- adds the current source/transcribed SRT as a selectable subtitle track;
- stream-copies local video at Original quality by default;
- uses MKV as the safest multi-track default, with MP4 available for compatible streams.

## Smart transcription recovery

The existing anti-hallucination guard remains primary. DubLocal does not globally loosen Whisper thresholds.

Instead, DubLocal selectively inspects a small set of suspicious regions after the primary transcription:

- long subtitle segments containing unusually few words;
- for the Accurate music profile only, short internal holes bounded by real subtitle text.

A candidate recovery is accepted only when two isolated no-context decoding passes agree closely. Output that merely repeats a neighbouring subtitle is rejected. Sparse-line replacement must add meaningful words while remaining related to the original line.

This is deliberately asymmetric: DubLocal prefers leaving an uncertain gap over inserting invented speech.

## Subtitle-source UX

YouTube can expose a very large automatic-caption catalogue because the source caption is accompanied by machine-translated variants for many languages. DubLocal does not present that raw catalogue as if every entry were an equivalent source subtitle track.

The normal **Available subtitles** selector:

- uses human language names rather than raw codes such as `aa` or `en-orig`;
- shows creator-provided caption tracks;
- shows genuine/original YouTube automatic-caption tracks;
- hides YouTube's mass machine-translated variants from the normal list when the original track can be identified;
- reports how many machine-translated variants were hidden and directs the user to DubLocal's own Translate stage instead;
- keeps the complete raw inventory internally for diagnostics/future advanced controls.

Local embedded subtitle tracks are also shown with human-readable language/type descriptions rather than raw codec/language identifiers.

## M1 / low-memory Macs

No additional AI model is loaded for these refinements. Mixing uses FFmpeg. Native timing reuses the same Kokoro worker/model and regenerates only lines that need a timing adjustment. Smart transcription recovery reuses the already installed Whisper model and only rechecks short ranges.

On Apple-Silicon Macs with less than 12 GiB memory, the extra transcription-recovery work is capped at three regions and 24 seconds of audio per transcription. There is no hidden second full-video transcription pass.
