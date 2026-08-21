# Regulatory atlas release format

The C01-C04 release is a content-addressed, bounded publication manifest. The
release builder accepts an evaluation report, quality-gate report, replay
report, accepted-only bundle, and the selected fixture. It produces a manifest
with a deterministic release identity and an explicit state:

- `published`: every release check passes;
- `review`: execution and quality pass but another release check requires
  inspection;
- `blocked`: a required execution or quality prerequisite fails.

## Manifest shape

The JSON manifest has these fields:

```json
{
  "release_id": "regulatory-atlas-c01-c04",
  "fixture_id": "regulatory-atlas-public-aggregate",
  "fixture_version": "2026.08.d05-c01-c04.v1",
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

The `checks` field contains twelve short, independently addressed checks:

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

The manifest address covers the release ID, fixture identity, state, checks,
and upstream addresses. Verification recomputes the manifest and check
addresses. A manifest with a changed context or upstream address fails
verification even if its state text still says `published`.

## Bundle formats

`RegulatoryAtlasBundleBuilder` supports JSON, CSV, and Markdown. JSON includes
the full sanitized entry shape. CSV is suitable for tabular review. Markdown
is a compact reviewer view. Every format includes record ID, operation, role,
state, bounded counts, issue codes, acceptance, and content address.

When `--accepted-only` is set, exactly four positive entries are allowed. The
twelve controls remain available in the full bundle and in the evaluation
receipts; accepted-only filtering is a publication view, not data deletion.

No bundle entry contains input text, payload dictionaries, source collections,
or subject-level identifiers. The builder verifies this property before
writing a file.

## Runtime stage order

The runtime emits nine stage receipts in this order:

```text
data -> evaluation -> replay -> scenarios -> lineage -> quality_gate
     -> reconciliation -> bundle -> context
```

The runtime is published only when all stage receipts pass. The context stage
compares the request with the exact fixture context key. A context mismatch is
not silently transported to another profile.

## Release command

```powershell
python -m glio_noncode build-regulatory-atlas-release examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-release.json
```

The release command evaluates the fixture and quality gate, replays the
evaluation, builds the accepted-only bundle, verifies the manifest, and writes
the JSON file only when its addresses and state are internally valid. The
repository workflow runs the same command against the checked-in descriptor.
