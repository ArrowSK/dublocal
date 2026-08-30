# DubLocal 0.6.0b6

Beta 6 targets end-to-end processing time without changing the translation model, subtitle safety checks, voice model, audio mix, output profile, or media-quality policy.

The trigger was a roughly nine-minute, highly fragmented YouTube-caption job that completed successfully in beta 5 but took about ten minutes end to end. On this shape of source, the main avoidable cost is repeated contextual-translation prompt/KV work: hundreds of very short caption fragments cause the same several-thousand-token programme context to be processed across many local Qwen calls.

## Faster contextual translation without a lower-quality mode

DubLocal keeps the same hardware-selected Qwen model and the same contextual prompt, validation and recovery rules. Beta 6 changes only how efficiently that work is scheduled.

### Larger optimistic batches for tiny fragmented captions

Normal sentence-sized subtitles keep the established limits: up to 48 lines on Qwen3 8B and 36 on Qwen3 4B.

When the timeline is both unusually dense and made of genuinely short caption fragments, DubLocal can begin with a larger optimistic batch: up to 96 lines on 8B or 72 on 4B. A moderately fragmented timeline can use an intermediate 72/54 ceiling.

This does not weaken alignment safety. Every response still has to preserve every subtitle ID and pass target-language validation. If a large attempt does not align cleanly, the existing adaptive fallback halves only that section until it reaches the established 12-line safety floor. No ambiguous SRT is accepted.

### Runtime context follows the programme's real context budget

Hardware recommendations still cap the maximum contextual model footprint, but a short programme no longer allocates a large KV cache merely because the Mac could support it.

DubLocal now derives the runtime allocation from the programme context budget that the translation prompt can actually use, plus the existing generation/headroom margin. This reduces avoidable unified-memory pressure without removing any source context from the prompt.

### llama.cpp prompt reuse when the installed runtime supports it

Current llama.cpp servers can expose `--cache-reuse`. Beta 6 detects support before enabling it and otherwise keeps the established server command unchanged. When available, a conservative 64-token reuse threshold lets llama.cpp retain exact reusable prompt chunks across adjacent translation requests.

This is an execution optimization only: the model, prompt text, sampling settings and validation rules are unchanged.

## What beta 6 deliberately does not change

- Qwen3 8B/4B hardware selection is unchanged.
- The senior review pass remains controlled by the existing hardware-quality recommendation; it is not disabled to gain speed.
- Translation recovery and the refusal to write an ambiguously aligned SRT remain intact.
- Kokoro generation, native timing correction, voice matching and audio mixing are unchanged.
- Output Profiles from beta 5 remain unchanged.
- Shareable MP4 bitrate/quality targets remain unchanged.

## Validation boundary

Regression tests cover dense-caption batch selection, preservation of normal subtitle batch limits, actual programme-context allocation, conditional llama.cpp cache-reuse activation and restoration of the established translation state after each call.

The exact real-world speedup depends on the installed llama.cpp build, subtitle fragmentation and how much of the total job is translation versus TTS/media work. Beta 6 therefore does not claim a fixed percentage improvement. The useful validation is to rerun the same source and compare total elapsed time.

## Updating

Existing packaged beta users can use **Settings → Updates → Update DubLocal**.

New users can download `DubLocal-0.6.0b6-macOS-unsigned.dmg` from this release.

The beta remains unsigned and not notarized, so macOS may require **Open Anyway** on first launch.
