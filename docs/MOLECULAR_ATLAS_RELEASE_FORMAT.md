# Molecular atlas release format

The C05-C08 release is a content-addressed publication manifest built from a
fixture evaluation, quality gate, replay report, accepted-only bundle, and the
selected public aggregate fixture.

## Release state

- `published`: every release check passes;
- `review`: evaluation and quality pass but another release check needs review;
- `blocked`: a required execution or quality prerequisite fails.

The release state is derived from checks. It is not a free-form status field.

## Manifest shape

```json
{
  "release_id": "molecular-atlas-c05-c08",
  "fixture_id": "molecular-atlas-public-aggregate",
  "fixture_version": "2026.08.d05-c05-c08.v1",
  "context_key": "GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown",
  "state": "published",
  "checks": [],
  "evaluation_address": "sha256:...",
  "quality_address": "sha256:...",
  "replay_address": "sha256:...",
  "bundle_address": "sha256:...",
  "content_address": "sha256:..."
}
```

The manifest includes twelve independently addressed checks:

1. release identity is declared;
2. fixture IDs agree;
3. fixture versions agree;
4. context keys agree;
5. evaluation is accepted;
6. quality gate is accepted;
7. replay is accepted;
8. bundle verification is empty;
9. four positive receipts are present;
10. review controls are excluded from the accepted-only bundle;
11. the evaluation address chain is closed;
12. the bundle contains no input collections.

Verification recomputes the manifest and every check address. A changed
context, upstream address, state, or check detail fails verification.

## Bundle formats

`MolecularAtlasBundleBuilder` supports JSON, CSV, and Markdown. Each entry
contains record ID, operation, role, state, bounded counts, issue codes,
acceptance, and a content address. No entry contains input text, payload
dictionaries, source collections, or subject identifiers.

With `--accepted-only`, exactly four positive entries are allowed. The twelve
controls remain available in the full evaluation and full bundle. Filtering is
a publication view and does not erase review evidence.

## Runtime order

The runtime emits nine stage receipts:

```text
data -> evaluation -> replay -> scenarios -> lineage -> quality_gate
     -> reconciliation -> bundle -> context
```

The runtime is published only when all stage receipts pass. The context stage
compares the request to the exact fixture context key.

## Release command

```powershell
python -m glio_noncode build-molecular-atlas-release examples/molecular-atlas-public-aggregate.json --output molecular-atlas-release.json
```

The command evaluates the fixture and quality gate, replays the evaluation,
builds the accepted-only bundle, verifies the manifest, and writes only a
content-addressed JSON result.
