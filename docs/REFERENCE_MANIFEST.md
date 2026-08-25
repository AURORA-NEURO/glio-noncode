# Reference manifest and adapter conformance

The generic reference boundary is a metadata contract for source adapters. It
does not copy a reference payload and it does not turn source availability into
scientific validity. A manifest records the receipt needed to decide whether a
bounded adapter may be invoked:

- a stable artifact and adapter identity;
- source, release, version, URI, and schema version;
- license and declared access mode;
- coordinate system and supported context keys;
- channels, retrieval policy, size, and optional SHA-256 checksums; and
- an explicit availability state and content address.

The exchange version is `reference-manifest-v1`. Artifact rows are sorted by
`artifact_id` before the manifest address is computed. Reopening a manifest
requires every artifact address and the manifest address; counts are checked
against the rows rather than trusted as supplied metadata.

## Manifest projections

The default manifest is built from the checked-in human reference assembly
registry and contains metadata receipts for GRCh37 and GRCh38. It contains no
sequence, annotation payload, subject identifier, credential, attribution,
model, or programming-language field.

```powershell
glio-noncode reference-manifest --format json --output reference-manifest.json
glio-noncode reference-manifest --format summary --output reference-summary.json
glio-noncode reference-manifest --format markdown --output reference-manifest.md
glio-noncode reference-manifest --format csv --output reference-manifest.csv
glio-noncode reference-manifest-schema --output reference-manifest-schema.json
```

Queries preserve stable manifest order and return receipt rows only:

```powershell
glio-noncode reference-manifest `
  --adapter-id reference-assembly-registry `
  --context GRCh38 `
  --limit 25 `
  --output reference-query.json
```

The equivalent service projections are:

```text
GET /v1/reference/manifest
GET /v1/reference/manifest/summary
GET /v1/reference/manifest/schema
GET /v1/reference/manifest/query?context=GRCh38&limit=25
```

Non-loopback deployment profiles apply their normal read scope and audit
policy to these routes. Query limits are bounded, repeated parameters are
rejected, and invalid state, offset, or limit values return a typed validation
error.

## Adapter conformance

`conform_adapter` accepts an `EvidenceAdapter`, a verified manifest, and a
bounded tuple of `AdapterConformanceProbe` values. Each probe repeats element
resolution and claim collection so the report can detect nondeterminism. It
checks:

1. required metadata and a matching manifest receipt;
2. available receipt state, version, license, and channel coverage;
3. tuple return types and typed `CandidateElement` / `EvidenceClaim` rows;
4. unique element identities and exact requested context;
5. claim source continuity to the manifest receipt;
6. bounded expected element and claim counts; and
7. recursive public-boundary keys in returned projections.

The report uses `adapter-conformance-v1` and retains every check, observed
value, required value, detail, invocation count, element count, claim count,
and content address. A missing or quarantined receipt is `blocked`; a runtime
or output failure is `review`; only a fully passing report is `accepted`.
No failure is converted into an empty success.

For portable CLI execution, the input document has this shape. The manifest
object below is abbreviated; use a previously emitted and verified manifest
from the `reference-manifest` command in an actual conformance input:

```json
{
  "manifest": { "version": "reference-manifest-v1", "artifacts": [] },
  "metadata": {
    "adapter_id": "fixture-adapter",
    "display_name": "Fixture adapter",
    "version": "2026.08",
    "license": "synthetic-fixture",
    "data_access": "local_fixture",
    "supported_contexts": ["GRCh38|glioma|adult|stem_like|unknown|unknown"],
    "channels": ["regulatory_element"],
    "failure_modes": ["missing_context"]
  },
  "elements": [],
  "probes": [
    {
      "probe_id": "empty-fixture",
      "variant_id": "v1",
      "context": {
        "genome_build": "GRCh38",
        "disease_class": "glioma",
        "age_group": "adult",
        "cell_state": "stem_like"
      },
      "expected_element_ids": []
    }
  ]
}
```

Run it with:

```powershell
glio-noncode adapter-conformance adapter-input.json --output adapter-conformance.json
glio-noncode adapter-conformance adapter-input.json --format markdown --output adapter-conformance.md
glio-noncode adapter-conformance-schema --output adapter-conformance-schema.json
```

The CLI returns exit code `0` only for an accepted report and `2` for review or
blocked conformance. The report contains checks and metadata addresses, not
the source payload. The public API does not accept arbitrary adapter code;
adapter execution remains an explicit local integration boundary.

## Review boundary

A passing manifest means that the receipt is structurally usable for its
declared context and access mode. A passing adapter report means that the
adapter behaved deterministically for the supplied probes. Neither result
proves source completeness, assay quality, biological effect, calibration,
clinical utility, or institutional authorization. Missing, stale, or
out-of-context sources remain visible and must be resolved or explicitly
abstained from by the downstream evidence runtime.
