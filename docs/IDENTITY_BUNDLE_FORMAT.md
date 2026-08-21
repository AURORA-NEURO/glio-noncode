# Identity evidence bundle format

This document defines the portable bundle emitted by
`IdentityEvidenceBundleBuilder`. The format is designed for deterministic
review, compact transfer, and replay without copying raw identity payloads.

## Version and scope

The bundle is derived from an `identity-evidence-v1` fixture and contains
evidence for Domain 01 capabilities C09-C12. It is a research software receipt.
It does not attest to specimen identity, consent, clinical meaning, digital
signatures, or institutional custody.

The bundle includes fixture identity and version, exact context, sorted public
source IDs, combined quality state, compact entries, component summaries, the
four-operation contract manifest, the evidence boundary, and a SHA-256 address.

## JSON shape

Canonical JSON is sorted by key and ends with one newline.

```json
{
  "accepted": true,
  "bundle_id": "identity-public-aggregate-001:identity-evidence",
  "component_summaries": {
    "contracts": {"content_address": "sha256:...", "contract_count": 4},
    "data": {
      "content_address": "sha256:...",
      "negative_control_count": 8,
      "positive_count": 4,
      "state": "accepted"
    },
    "fixture": {"check_count": 37, "content_address": "sha256:...", "state": "accepted"},
    "quality": {
      "check_count": 12,
      "content_address": "sha256:...",
      "failed_check_ids": [],
      "passed": true,
      "state": "accepted"
    },
    "scenarios": {
      "content_address": "sha256:...",
      "failed_scenario_ids": [],
      "scenario_count": 12,
      "state": "accepted"
    }
  },
  "content_address": "sha256:...",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "contract_manifest": {
    "content_address": "sha256:...",
    "contract_count": 4,
    "contract_version": "identity-contracts-v1",
    "contracts": []
  },
  "entry_count": 12,
  "entries": [],
  "evidence_boundary": "Public aggregate identifiers and deterministic software receipts only.",
  "fixture_id": "identity-public-aggregate-001",
  "fixture_version": "identity-evidence-v1",
  "positive_entry_count": 4,
  "quality_state": "accepted",
  "review_entry_count": 8,
  "source_ids": ["ncbi-clinvar-rs121913502", "ncbi-grch38-reference-assembly"]
}
```

The `contracts` array is abbreviated in the example. The actual output
contains full required/output field declarations and external boundaries.

## Entry shape

Each entry has these semantic fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `entry_id` | string | Stable positive or `negative:` control identity |
| `entry_class` | string | `positive` or `review` |
| `kind` | string | `equivalence`, `reconciliation`, `sample`, or `custody` |
| `state` | string | Operation state such as `supported`, `partial`, or `contradictory` |
| `source_id` | string | Public source receipt identity |
| `public_identifier` | string | Non-sensitive public trace identity |
| `content_address` | string | Address of the operation receipt |

The entry is not a copy of the operation report. It does not include raw
variant alleles, observation rows, subject metadata, event actor metadata,
source URLs, or free-form payload attributes.

Positive entries are emitted in fixture record order. Review entries are
emitted in fixture control order. The order contributes to the bundle address.

## State semantics

`quality_state=accepted` means every component gate passed. It does not mean
every entry has state `supported`: the positive reconciliation entry is
expected to be `partial`, and review entries retain their review states.

`quality_state=review` means at least one gate failed. The bundle remains
serializable so a reviewer can inspect failed component receipts.

The `accepted` boolean is derived and is not part of the address body.

## Component summaries

The summary fields are intentionally small:

- `data` reports boundary state, positive count, negative count, and audit address;
- `fixture` reports evaluator state, check count, and evaluator address;
- `quality` reports gate state, pass/fail, failed IDs, count, and gate address;
- `scenarios` reports matrix state, count, failed IDs, and matrix address; and
- `contracts` reports contract count and manifest address.

Full component reports remain available from individual CLI commands. The
summary is not a replacement for them.

## Content-address semantics

The bundle address is computed from this body:

```text
bundle_id
fixture_id
fixture_version
context_key
source_ids
quality_state
entries
component_summaries
contract_manifest
evidence_boundary
```

The body is serialized with the repository canonical JSON serializer: sorted
keys, compact separators, UTF-8 encoding, and enum values. The SHA-256 address
is formatted as `sha256:<64 lowercase hexadecimal characters>`.

Derived convenience fields are added only after hashing:

- `accepted`;
- `entry_count`;
- `positive_entry_count`; and
- `review_entry_count`.

`IdentityEvidenceBundleBuilder.verify()` removes those fields and recomputes
the body address. It returns false for a non-mapping, missing address,
non-string address, or changed body field.

## CSV rendering

CSV contains one header row and one row per entry. The header is fixed:

```text
entry_id,entry_class,kind,state,source_id,public_identifier,content_address
```

CSV is useful for tabular review but does not contain component summaries,
contract declarations, or the evidence boundary. Retain JSON alongside CSV
when the complete receipt is required.

## Markdown rendering

Markdown contains bundle identity, fixture/version, context, quality state,
bundle address, evidence boundary, and an entry table. It renders stable entry
IDs and operation addresses rather than raw operation payloads.

## Writing bundles

Filename suffix inference is supported when no explicit format is supplied:

```python
from glio_noncode.identity_bundle import IdentityEvidenceBundleBuilder

builder = IdentityEvidenceBundleBuilder()
builder.write("examples/identity-public-aggregate.json", "identity.json")
builder.write("examples/identity-public-aggregate.json", "identity.csv")
builder.write("examples/identity-public-aggregate.json", "identity.md")
```

An explicit format takes precedence over a recognized suffix:

```python
builder.write(
    "examples/identity-public-aggregate.json",
    "identity.json",
    output_format="markdown",
)
```

An unrecognized suffix defaults to JSON. Invalid format values raise
`ValueError`; blank custom bundle IDs raise `ValidationError`.

## CLI forms

```powershell
glio-noncode build-identity-bundle examples/identity-public-aggregate.json --output identity.json
glio-noncode build-identity-bundle examples/identity-public-aggregate.json --output identity.csv --format csv
glio-noncode build-identity-bundle examples/identity-public-aggregate.json --output identity.md --format markdown
```

The command exits zero when the combined quality state is accepted and exits 2
when a review bundle is emitted. The output is still written on review.

## Privacy and retention

Bundle builders must not add raw fixture payloads to entries, summaries, or
Markdown tables. If a future operation adds a restricted field, the data audit
must review the fixture and bundle tests must prove that the restricted value
does not appear in serialized reports.

Public identifiers are retained only when declared as aggregate trace
identities. A public identifier is not a person identifier. The bundle must
never be used as a patient-level data store.

Source URLs and license details remain in the fixture and data audit report,
not in compact entries. This keeps trace receipts separate from full
provenance records.

## Versioning and compatibility

Changes to entry fields, body fields, address rules, or contract manifest shape
require a new bundle format version and a new verifier test. Adding an operation
kind requires:

1. a public data record kind;
2. a contract declaration;
3. evaluator and scenario execution;
4. replay and quality count floors;
5. compact-entry tests;
6. CLI and CI coverage; and
7. documentation of the external validation boundary.

Reordering existing entries changes the content address. Consumers should
treat the address as a complete receipt identity, not an in-place database key.

## Verification checklist

Before publishing a bundle:

- run the data audit;
- run the 37-check evaluator;
- run replay with required context;
- run the twelve-scenario matrix;
- inspect the four-operation contract manifest;
- run the combined twelve-check gate;
- verify the JSON content address;
- compare positive and review counts;
- confirm source IDs are sorted;
- confirm entry IDs and addresses are unique; and
- retain full fixture and component reports beside the compact bundle.
