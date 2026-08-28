# Local TTS providers

DubLocal resolves voice generation as **language → compatible local TTS provider**. Official Kokoro remains the default provider for its supported languages; third-party or user-registered providers can cover additional languages without pretending they are official Hexgrad frontends.

## Built-in policy

| Language | Default local provider | Status |
| --- | --- | --- |
| English (US/UK), Spanish, French, Hindi, Italian, Brazilian Portuguese, Japanese, Mandarin | `hexgrad/Kokoro-82M` | Official Kokoro path, unchanged |
| Russian | `zaakirio/kokoro-ru` v2 | Vetted third-party provider; explicit preparation required |
| Ukrainian | none | Intentionally not enabled pending stronger voice/data provenance review |

Russian exposes Sveta, Masha and Dima. Internal voice IDs preserve DubLocal's lightweight vocal-range matching convention (`rf_*` / `rm_*`) without claiming that Russian is an official Kokoro language.

## Fork resilience

A remote provider is a **source for preparation**, not a runtime dependency.

When a provider is prepared DubLocal:

1. resolves the manifest's pinned revision to the exact upstream commit;
2. downloads only the declared provider assets;
3. verifies declared SHA-256 values;
4. validates required config/model/voice files and, for Russian, the acute-aware eSpeak data;
5. copies the resulting snapshot to persistent DubLocal application data;
6. writes an `install-receipt.json` containing the manifest, resolved revision, required files and fingerprints.

Normal synthesis uses that persistent local directory. It does not call the `kokoro-ru` repository. Therefore deletion, renaming or breakage of that fork does not invalidate an already prepared Russian provider.

A first-time installation still needs a source. If the original source is gone, a user can register a compatible pinned mirror or a local directory provider and prepare that instead.

Generated voice manifests record the provider ID, provider licence metadata and local install receipt so output provenance can be traced later.

## Russian frontend boundary

The Russian provider uses:

- local Kokoro-compatible v2 weights and voice packs;
- RUAccent for stress, `ё` restoration and homograph handling;
- a small DubLocal Russian frontend for normalization and Kokoro-vocabulary mapping;
- the separately installed `espeak-ng` executable with the provider's acute-aware local eSpeak data.

DubLocal does **not** import or bundle the GPL Python `phonemizer` package for this path. eSpeak NG itself is GPL-3.0+ and remains an external executable. This boundary reduces packaging/licensing coupling; it is not a legal opinion that all possible distribution arrangements are automatically compliant.

Russian runs on CPU by default. That is intentional: it is the compatibility baseline across Apple Silicon generations and avoids making Russian support depend on model-specific PyTorch MPS behavior.

## Custom providers: models, not code plugins

Custom support is deliberately narrower than a general plugin system. A provider is a JSON manifest describing files that an **already audited DubLocal backend/frontend** can load. The manifest cannot introduce executable code.

Currently accepted backend:

- `kokoro-local`

Currently accepted frontends:

- `russian-v2`
- `official-a`, `official-b`, `official-e`, `official-f`, `official-h`, `official-i`, `official-j`, `official-p`, `official-z`

This allows compatible alternative weights/voice packs for known Kokoro phoneme frontends, while keeping the executable inference and G2P code inside DubLocal's review boundary.

The validator rejects fields such as `code`, `command`, `entrypoint`, `module`, `python`, `script` and `shell`.

### Source types

A provider may use either:

- `huggingface`: requires `owner/repository`, an immutable 7–40 character hexadecimal revision, and SHA-256 pins for every declared config/model/voice asset;
- `local`: an existing local directory; checksums are optional but are verified when supplied.

Mutable references such as `main` are rejected for remote custom providers.

### Required licence metadata

Every provider must declare:

- licence identifier;
- explicit `commercial_use: true` or `false`;
- redistribution policy;
- licence/model-card source;
- attribution text.

DubLocal records these declarations; it does not certify that a third-party uploader actually owns every underlying right. For commercial distribution, the user or publisher remains responsible for reviewing the model/data/voice chain of rights.

## Example local mirror

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
