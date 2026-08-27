# DubLocal quality notes

This document records the quality policy behind `v0.4.2.dev0`. It exists because “AI translation quality” is not one problem: transcription accuracy, context, model capability, target-language fluency and subtitle alignment can fail independently.

## Quality hierarchy

DubLocal treats the pipeline in this order:

```text
audio/source media
  → source subtitle accuracy
  → stable timing/IDs
  → contextual translation
  → target-language review
  → structural/output validation
  → optional TTS
```

A later stage must not pretend it can reliably repair an earlier unknown. In particular, translation context is not permission to invent what an automatic captioner probably misheard.

## Source subtitle quality

Creator/embedded text subtitles are preserved as supplied.

YouTube automatic captions are explicitly marked as automatic. When their wording is clearly damaged, the recommended quality path is to transcribe the audio locally with the Accurate Large-v3-Turbo-Q5 Whisper option rather than ask the translator to hallucinate the original lyric/dialogue.

## Translation model policy

The v0.4.1 Qwen3 4B development backend was replaced as the recommended translator after real-language testing showed unacceptable literal grammar, word choice and occasional mixed-script output.

v0.4.2 Best quality uses pinned Qwen3 8B Q4_K_M through llama.cpp.

The model is heavier (~5.03 GB) and Best quality normally uses a second review pass. This is an intentional quality/latency trade-off. OPUS remains the explicit smaller/faster option.

## Context policy

Context grows with programme duration up to a bounded input ceiling. It combines programme-wide samples, nearby source dialogue and recent translations.

Short media uses larger target chunks so a song or short clip can normally be understood as one coherent local section rather than many disconnected calls.

## Target-language policy

Prompts include language-specific guidance where useful. Russian currently requires natural contemporary Russian grammar, discourages English calques and pseudo-Russian transliteration, and preserves source profanity/register.

A second review pass compares draft translation against source/context and is asked to correct semantic mistakes, grammar, calques, unnatural word choice and untranslated ordinary words.

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

Even Qwen3 8B plus review is not represented as equivalent to a professional translator. The side-by-side Original/Translation preview remains part of the product because semantic nuance, humour, lyric interpretation and cultural adaptation are not fully machine-verifiable.

Quality regressions should be reported with the smallest lawful source/translation sample that reproduces them, together with whether the source timeline came from creator subtitles, automatic captions or local Whisper.
