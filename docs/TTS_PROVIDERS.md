# Local TTS providers

DubLocal resolves voice generation as **language → compatible local TTS provider**. Official Kokoro remains the default provider for its supported languages. Vetted built-in providers cover additional languages, while user-registered Kokoro-compatible providers remain data-only manifests rather than executable plugins.

## Built-in policy

| Language | Default local provider | Status |
| --- | --- | --- |
| English (US/UK), Spanish, French, Hindi, Italian, Brazilian Portuguese, Japanese, Mandarin | `hexgrad/Kokoro-82M` | Official Kokoro path, unchanged |
| Hungarian | macOS `hu_HU` system voice when installed; otherwise Piper | Built-in cross-platform route |
| Russian | `zaakirio/kokoro-ru` v2 | Vetted third-party provider; explicit preparation required |
| Ukrainian | none | Intentionally not enabled pending stronger voice/data provenance review |

## Hungarian provider

Hungarian is intentionally not tied to an Apple-only API.

On **macOS**, DubLocal detects installed `hu_HU` voices from the system voice catalogue. Auto prefers the installed system Hungarian voice; Piper remains available as a selectable alternative. The system voice is invoked through the operating system and converted to DubLocal's normal mono PCM WAV contract with FFmpeg.

On **Windows and other platforms**, the system-voice branch does not exist and the Hungarian choices are Piper only. The initial Piper set is:

- Anna · female
- Berta · female
- Imre · male

The voice files come from `rhasspy/piper-voices` at an immutable revision recorded in the code and installation receipt. The Hungarian voice model/config assets are verified before use. Upstream metadata identifies the voice repository/model files as MIT-licensed and the Hungarian source datasets as CC0.

Current Piper is GPL-3.0-or-later. DubLocal therefore does not import Piper into its Apache-2.0 process. Preparing Hungarian Piper creates a dedicated local virtual environment, installs the pinned `piper-tts` runtime there, and invokes it out of process. This is an architectural/licensing boundary, not a legal opinion about every possible distribution arrangement.

Piper preparation is explicit. A Standard workflow job will not silently install a runtime or download a voice model halfway through processing. Prepare the desired Hungarian Piper voice in Model Manager first. An installed macOS system voice requires no model download.

Hungarian timing uses the existing timed-SRT contract. Each segment gets a normal-speed pilot. Only material overflow is regenerated at a provider-native faster rate, up to the supported 2× limit. Subtitle timestamps are not rewritten and this provider does not use post-generation waveform stretching.

macOS system voices are operating-system resources and are not bundled or redistributed by DubLocal. DubLocal does not assert separate commercial-use or redistribution rights for their generated output; applicable platform/vendor terms remain relevant.

## Russian provider

Russian exposes Sveta, Masha and Dima. Internal voice IDs preserve DubLocal's lightweight vocal-range matching convention (`rf_*` / `rm_*`) without claiming that Russian is an official Kokoro language.

A remote provider is a **source for preparation**, not a runtime dependency. When the Russian provider is prepared DubLocal resolves the pinned source, verifies declared assets, stores a persistent local snapshot, and records an installation receipt. Normal synthesis uses that local copy rather than consulting the model fork again.

The Russian frontend uses local Kokoro-compatible v2 weights/voice packs, RUAccent, a small DubLocal normalization frontend, and the separately installed `espeak-ng` executable with the provider's acute-aware local eSpeak data. DubLocal does not import or bundle the GPL Python `phonemizer` package for this path. Russian runs on CPU by default as the compatibility baseline across Apple Silicon generations.

## Custom providers: models, not code plugins

Custom support is deliberately narrower than a general plugin system. A provider is a JSON manifest describing files that an **already audited DubLocal backend/frontend** can load. The manifest cannot introduce executable code.

Currently accepted custom backend:

- `kokoro-local`

Currently accepted custom frontends:

- `russian-v2`
- `official-a`, `official-b`, `official-e`, `official-f`, `official-h`, `official-i`, `official-j`, `official-p`, `official-z`

Hungarian Piper is a built-in audited provider and is not exposed through this Kokoro-specific custom-provider manifest schema.

The custom-provider validator rejects fields such as `code`, `command`, `entrypoint`, `module`, `python`, `script` and `shell`.

### Source types

A custom provider may use either:

- `huggingface`: requires `owner/repository`, an immutable 7–40 character hexadecimal revision, and SHA-256 pins for every declared config/model/voice asset;
- `local`: an existing local directory; checksums are optional but are verified when supplied.

Mutable references such as `main` are rejected for remote custom providers.

### Required licence metadata

Every custom provider must declare:

- licence identifier;
- explicit `commercial_use: true` or `false`;
- redistribution policy;
- licence/model-card source;
- attribution text.

DubLocal records these declarations; it does not certify that a third-party uploader actually owns every underlying right. For commercial distribution, the user or publisher remains responsible for reviewing the model/data/voice chain of rights.

## Example local Kokoro-compatible mirror

```json
{
  "schema_version": 1,
  "id": "my-russian-kokoro",
  "label": "My vetted Russian Kokoro mirror",
  "language": "ru",
  "language_label": "Russian",
  "backend": "kokoro-local",
  "frontend": "russian-v2",
  "source": {
    "type": "local",
    "path": "/Users/me/Models/my-russian-kokoro"
  },
  "license": {
    "id": "OpenRAIL",
    "commercial_use": true,
    "redistribution": "not-bundled",
    "source": "model-card-or-license-location",
    "attribution": "required attribution text"
  },
  "config_file": "kokoro-config.json",
  "voices": [
    {
      "id": "rf_sveta",
      "label": "Sveta · female",
      "gender": "female",
      "model_file": "kokoro-ru-v2-base.pth",
      "voice_file": "voices/sveta.pt"
    }
  ],
  "default_voice": "rf_sveta",
  "preferred": true
}
```

After registration, prepare the provider from Settings. A prepared preferred custom provider is selected before the built-in Russian provider after restart.

## Remote custom-provider integrity

For a remote manifest add a `checksums` object, for example:

```json
{
  "source": {
    "type": "huggingface",
    "repo_id": "owner/repository",
    "revision": "0123456789abcdef0123456789abcdef01234567"
  },
  "checksums": {
    "kokoro-config.json": "<64-hex-sha256>",
    "model.pth": "<64-hex-sha256>",
    "voices/voice.pt": "<64-hex-sha256>"
  }
}
```

The exact resolved commit and verification data are retained in the local installation receipt.
