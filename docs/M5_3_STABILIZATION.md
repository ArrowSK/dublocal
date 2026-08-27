# M5.3 stabilization notes

This stabilization layer keeps the existing DubLocal workflow and public M5/M5.1 APIs. It addresses issues found in full end-to-end music-video tests without introducing a heavy source-separation dependency.

## Dubbed soundtrack balance

DubLocal now keeps the original soundtrack at a reduced, stable bed level throughout the programme. During subtitle dialogue/singing windows the original mix is suppressed further, while the generated voice stays foreground. A gentle compressor and limiter bound the final mix so the level does not jump back to the full original soundtrack between dubbed lines.

This is intentionally lightweight DSP. Professional dubbing normally uses a dialogue-free M&E stem; consumer media usually does not provide one. DubLocal therefore uses dialogue-window ducking rather than pretending it can perfectly remove vocals from a mixed soundtrack.

The approach follows the same general principle as dialogue-anchored loudness workflows: foreground dialogue should remain intelligible and programme loudness range should be controlled, not merely peak-limited.

## Per-line timing

Generated voice remains anchored to the source subtitle start/end window. M5.3 expands the available FFmpeg `atempo` range by chaining legal 0.5x–2.0x stages, allowing an effective 0.30x–2.50x timing correction. A second small correction pass is used when duration rounding leaves the spoken end more than 25 ms away from the target.

Truly pathological stretches are still reported rather than forced. Subtitle timestamps themselves are never changed by voice fitting.

## Original media + subtitles only

The Export stage now also offers **Package original + subtitles · no dub**. This path:

- keeps the original audio untouched;
- does not add a DubLocal voice/dub track;
- does not add the translated subtitle track;
- adds the current source/transcribed SRT as a selectable subtitle track;
- stream-copies local video at Original quality by default;
- uses MKV as the safest multi-track default, with MP4 available for compatible streams.

## Smart transcription recovery

The existing anti-hallucination guard remains primary. M5.3 does not globally loosen Whisper thresholds.

Instead, DubLocal selectively inspects a small set of suspicious regions after the primary transcription:

- long subtitle segments containing unusually few words;
- for the Accurate music profile only, short internal holes bounded by real subtitle text.

A candidate recovery is accepted only when two isolated no-context decoding passes agree closely. Output that merely repeats a neighbouring subtitle is rejected. Sparse-line replacement must add meaningful words while remaining related to the original line.

This is deliberately asymmetric: DubLocal prefers leaving an uncertain gap over inserting invented speech.

## Subtitle-source UX

YouTube can expose a very large automatic-caption catalogue because the source caption is accompanied by machine-translated variants for many languages. DubLocal no longer presents that raw catalogue as if every entry were an equivalent source subtitle track.

The normal **Available subtitles** selector now:

- uses human language names rather than raw codes such as `aa` or `en-orig`;
- shows creator-provided caption tracks;
- shows genuine/original YouTube automatic-caption tracks;
- hides YouTube's mass machine-translated variants from the normal list when the original track can be identified;
- reports how many machine-translated variants were hidden and directs the user to DubLocal's own Translate stage instead;
- keeps the complete raw inventory internally for diagnostics/future advanced controls.

Local embedded subtitle tracks are also shown with human-readable language/type descriptions rather than raw codec/language identifiers.

## M1 / low-memory Macs

No additional AI model is loaded for these refinements. Timing and mixing use FFmpeg. Smart recovery reuses the already installed Whisper model and only rechecks short ranges.

On Apple-Silicon Macs with less than 12 GiB memory, the extra recovery work is capped at three regions and 24 seconds of audio per transcription. There is no hidden second full-video transcription pass.
