# DubLocal quality notes

This document records the quality policy behind `v0.4.2.dev0`. It exists because “AI translation quality” is not one problem: transcription accuracy, context, model capability, target-language fluency, hardware limits and subtitle alignment can fail independently.

## Quality hierarchy

DubLocal treats the pipeline in this order:

```text
audio/source media
  → source subtitle accuracy
  → stable timing/IDs
  → hardware-appropriate contextual translation
  → target-language review when the Mac can support the profile comfortably
  → structural/output validation
  → optional TTS
```

A later stage must not pretend it can reliably repair an earlier unknown. In particular, translation context is not permission to invent what an automatic captioner probably misheard.

## Source subtitle quality

Creator/embedded text subtitles are preserved as supplied.

YouTube automatic captions are explicitly marked as automatic. When their wording is clearly damaged, the recommended quality path is to transcribe the audio locally with the Accurate Large-v3-Turbo-Q5 Whisper option rather than ask the translator to hallucinate the original lyric/dialogue.

## Hardware-aware translation policy

DubLocal does not recommend the same model to every Mac.

The app detects architecture and physical memory locally and chooses a conservative profile. The normal Main UI therefore shows one clean choice: **Recommended for this Mac**. Model/RAM/context details live in Settings and the translation engine status rather than cluttering the workflow.

Current v0.4.2 policy:

| Mac class | Recommended model | Review | Effective input-context cap |
| --- | --- | --- | ---: |
| Apple Silicon below 12 GB (normally 8 GB M1/M2 class) | Qwen3 4B Q4_K_M | off | 8,192 |
| Apple Silicon 12–23 GB (normally 16 GB) | Qwen3 8B Q4_K_M | off | 16,384 |
| Apple Silicon 24 GB+ | Qwen3 8B Q4_K_M | on | 24,576 |
| Intel below 24 GB | Qwen3 4B Q4_K_M | off | 6,144 |
| Intel 24 GB+ | Qwen3 8B Q4_K_M | off | 12,288 |

These are deliberately cautious defaults rather than hard compatibility claims. The important constraint is unified/physical memory pressure and practical inference time, not the chip marketing name alone.

The llama.cpp runtime context allocation is reduced along with the prompt budget. On an 8 GB M1, DubLocal therefore does **not** start a 32k KV cache and merely feed it 8k of text; the actual local runtime receives a smaller context allocation as well. This is important for avoiding unnecessary swap pressure.

## Translation model policy

Real-language testing showed that Qwen3 4B was not acceptable as a universal “best quality” recommendation. It remains useful as the lightweight contextual model for low-memory Macs.

Qwen3 8B Q4_K_M is the balanced/best-quality model. On higher-memory Apple Silicon the Best profile adds a second review pass. The review reuses the same loaded model, so it increases processing time much more than peak model memory.

OPUS remains the explicit smaller/faster sentence-level option.

## Context policy

Context grows with programme duration up to the active hardware profile's bounded input ceiling. It combines programme-wide samples, nearby source dialogue and recent translations.

Short media uses larger target chunks so a song or short clip can normally be understood as one coherent local section rather than many disconnected calls.

## Target-language policy

Prompts include language-specific guidance where useful. Russian currently requires natural contemporary Russian grammar, discourages English calques and pseudo-Russian transliteration, and preserves source profanity/register.

When the selected hardware profile enables it, a second review pass compares draft translation against source/context and is asked to correct semantic mistakes, grammar, calques, unnatural word choice and untranslated ordinary words.

## Protected structural tags

A standalone bracketed cue such as `[MUSIC]` is structural subtitle information, not prose to translate. Protected tags bypass the model and are copied exactly.

## Validation policy

Automated validation is intentionally conservative. It can prove some things but not “the translation is beautiful”.

Before writing translated SRT, DubLocal verifies:

- subtitle IDs/order/timestamps remain aligned;
- no llama.cpp runtime/log/prompt content leaked into text;
- no unexpected CJK/Hangul contamination exists for current European targets;
- substantial wrong-script leakage is rejected;
- protected tags remain untouched.

If the model cannot produce validated output after contextual recovery, DubLocal stops instead of creating a plausible-looking corrupt file.

## Human quality boundary

Neither Qwen3 4B nor Qwen3 8B is represented as equivalent to a professional translator. The side-by-side Original/Translation preview remains part of the product because semantic nuance, humour, lyric interpretation and cultural adaptation are not fully machine-verifiable.

Quality regressions should be reported with the smallest lawful source/translation sample that reproduces them, together with whether the source timeline came from creator subtitles, automatic captions or local Whisper.
