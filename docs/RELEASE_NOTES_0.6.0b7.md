# DubLocal 0.6.0b7

Beta 7 adds local Hungarian voice-over while keeping the voice architecture portable beyond macOS.

## Hungarian voice-over

Hungarian (`hu`) is now a complete Standard-workflow target: DubLocal can translate the subtitle timeline to Hungarian and pass it directly into local voice generation.

The Auto provider policy is platform-aware:

- **macOS:** use an installed Hungarian (`hu_HU`) system voice when one is available; Piper remains selectable as a fallback/alternative.
- **Windows and other platforms:** use Piper. No Apple-only dependency is required by the Hungarian backend.

The initial Piper voice set is **Anna**, **Berta** and **Imre**. Voice model/config assets are fetched from the pinned `rhasspy/piper-voices` revision and verified before use. The Piper runtime is installed into a DubLocal-owned isolated virtual environment and invoked out of process rather than imported into DubLocal's Apache-2.0 application runtime.

## Timing and normal workflow behavior

Hungarian uses the same timed-SRT contract as the existing voice pipeline. Each line is synthesized at normal speed first. A line that materially exceeds its subtitle window is regenerated once at a provider-native faster speaking rate, up to the established 2× limit. Subtitle timestamps are not rewritten and no waveform time-stretch is introduced by this provider.

Standard/Auto remains simple: choose Hungarian as the output language and request Voice-over. Detailed mode exposes the available Hungarian voices like the other languages.

Piper preparation remains explicit. A generation job does not silently download the runtime or voice model; the user prepares the desired Hungarian voice from Model Manager first. An already-installed macOS system voice requires no model download.

## Portability guard

CI now includes a Windows job for the Hungarian provider and cross-platform voice-routing imports in addition to the existing Python 3.11/3.13 Linux test matrix. This is a portability guard for the backend, not a claim that DubLocal already ships a Windows installer.

## Licensing boundary

The pinned Hungarian Piper voice data records the upstream model/data licensing metadata in its installation receipt. Piper itself is a GPL-licensed runtime and is kept in a separate local virtual environment invoked out of process.

macOS system voices are operating-system resources. DubLocal does not redistribute them and does not assert separate commercial or redistribution rights for generated system-voice output; the applicable OS/vendor terms remain relevant.

## Validation boundary

Automated tests cover platform-aware voice selection, Hungarian translation-to-voice mapping, explicit Piper preparation, Windows/POSIX runtime paths, timed segment generation and selective overflow regeneration.

The real Anna/Berta/Imre model download and a real macOS Hungarian system voice are not exercised in CI because those paths require optional local assets. A real machine test remains the final validation for perceived voice quality.

## Updating

Existing packaged beta users can use **Settings → Updates → Update DubLocal**.

New macOS users can download `DubLocal-0.6.0b7-macOS-unsigned.dmg` from this release.
