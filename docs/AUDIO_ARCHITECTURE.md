# DubLocal audio architecture

DubLocal has two local soundtrack paths. The lightweight path is always available and remains the reliability baseline. The optional separated path is intended for music-heavy material where reducing the entire programme mix would unnecessarily suppress drums, bass and accompaniment together with the original singer.

## Timing policy

Kokoro timing treats each subtitle interval as a maximum available window, not a duration that must be filled.

1. Generate the line at the selected natural Kokoro speed.
2. If the line fits, keep that render and leave the remaining interval silent.
3. If the line overflows materially, regenerate it at a faster native Kokoro speed.
4. A correction pass may speed the line up again if overflow remains.
5. Adaptive timing never slows a line below the user's selected base speed merely to fill silence.
6. Export never uses FFmpeg `atempo` to stretch generated speech.

This avoids the low-speed prosody and articulation artifacts caused by forcing short translated lines to occupy long source-caption windows.

## Path A: dialogue / compatibility mix

This is the universal fallback and the normal route for ordinary spoken material.

- no source-separation model is required;
- the established subtitle-window dialogue suppression remains in place;
- the original soundtrack is kept as a quieter stable bed;
- the generated DubLocal voice is mixed over it;
- failure of the optional separation path in Auto mode falls back here instead of failing the render.

An 8 GB M1-class Mac therefore remains a supported first-class target even if no separation runtime/model is installed.

## Path B: music-aware separated mix

For music-heavy sources, DubLocal can separate the first programme audio track into:

- `vocals.wav` — original vocal/speech stem;
- `no_vocals.wav` — accompaniment stem.

The current backend is Demucs v4 in two-stem vocal mode. It runs in an isolated Python environment and does not inject packages into DubLocal or another application's environment.

The separated mix then:

1. keeps the accompaniment close to programme level;
2. ducks accompaniment only moderately while DubLocal speech is active;
3. suppresses the isolated original vocal strongly across the source-vocal window;
4. measures source-vocal and generated-segment RMS and applies bounded per-line gain matching;
5. searches a small window around each subtitle start for a clear onset in the isolated source-vocal stem;
6. delays the DubLocal segment only when the detected onset is later and the generated line has enough free timing slack;
7. mixes accompaniment + suppressed source vocal + aligned DubLocal voice through conservative compression and a final limiter.

The onset correction is intentionally one-sided and bounded. It does not move a dub earlier than the subtitle start, and it does not delay a line past the free time available before the subtitle end.

## Automatic routing

Simple / Magic Flow always requests `Auto`.

Auto uses a conservative music score based on strong subtitle music cues and source/title metadata. It selects separation only when:

- the material is strongly music-like; and
- a compatible separation runtime is already prepared.

It does not silently install a large optional runtime/model. If music is detected but the optional runtime is absent, DubLocal completes the job using the lightweight dialogue path.

Advanced exposes an explicit strategy choice:

- `Auto`;
- `Dialogue`;
- `Vocal separation`.

Explicit Vocal separation is permission to prepare the isolated runtime if needed. Model weights are then obtained by the upstream Demucs runtime on first separated render.

## Apple Silicon scaling

The architecture is memory-tiered rather than generation-specific.

| Unified memory | Default separation profile | Device | Segment policy |
| --- | --- | --- | --- |
| below 12 GiB | `htdemucs` | CPU | 4.0 s |
| 12–31 GiB | `htdemucs` | CPU | 7.0 s |
| 32 GiB and above | `htdemucs_ft` | CPU | 7.5 s |

CPU is the compatibility baseline because upstream Demucs explicitly documents the macOS CPU path. This avoids making the feature depend on MPS operator coverage that can differ across PyTorch/Demucs versions. Shorter segments reduce peak memory pressure on low-memory Macs. The fine-tuned model is reserved for high-memory hardware because it is substantially slower.

## Licensing and distribution

DubLocal does not bundle Demucs or Demucs weights. The upstream Demucs repository is MIT-licensed. Runtime/model preparation is optional and user initiated; packaged releases must continue to satisfy DubLocal's model/third-party manifest policy before any third-party weights or binaries are bundled or redistributed.

Nothing in this architecture grants rights to source media. The existing processing-rights confirmation remains unchanged.
