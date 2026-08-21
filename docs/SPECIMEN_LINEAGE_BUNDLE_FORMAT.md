# Domain 03 C09-C12 evidence bundle format

The specimen lineage bundle is a compact release projection of the public
aggregate evidence gate. It is designed for review, archival, and downstream
inspection without copying the raw adapter payload into the bundle.

## 1. Envelope

The JSON envelope uses schema `specimen-lineage-bundle-v1`:

```json
{
  "schema": "specimen-lineage-bundle-v1",
  "bundle_id": "specimen-lineage-c09-c12",
  "fixture_id": "specimen-lineage-public-aggregate-v1",
  "state": "accepted",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "source_ids": ["..."],
  "entries": [],
  "quality_address": "sha256:...",
  "lineage_address": "sha256:...",
  "content_address": "sha256:...",
  "entry_count": 12
}
```

`content_address` is computed over every field except itself and `entry_count`.
The entry count is derived from the entries and is present for inspection.
Changing an issue set, result address, quality address, source set, or context
changes the envelope address.

## 2. Entry schema

Every fixture record produces one entry:

| Field | Type | Contract |
| --- | --- | --- |
| `entry_id` | string | deterministic address-derived entry ID |
| `record_id` | string | fixture record identity |
| `operation` | string | one of four C09-C12 operation values |
| `fixture_state` | string | `accepted` or `review` |
| `result_state` | string | adapter result state |
| `issue_codes` | array of strings | sorted observed diagnostics |
| `source_ids` | array of strings | declared receipts shaping the row |
| `context_key` | string | exact six-dimension context |
| `record_address` | string | fixture record SHA-256 address |
| `result_address` | string | sanitized execution result SHA-256 address |

An entry has no `payload`, `records`, `observations`, patient fields, or raw
adapter dataclass. The entry is a receipt of the execution, not a data export.

## 3. Address rules

The fixture record address covers:

```text
record_id + operation + source_ids + context_key + fixture role
+ expected state + payload + parameters + issue codes + expected counts
```

The result address covers the sanitized operation projection. It includes state,
bounded IDs, counts, issue codes, and result addresses but excludes raw input
rows. The quality address covers all cross-surface release checks. The lineage
address covers source, fixture, record, result nodes and typed edges.

An address must begin with `sha256:`. The builder and verifier reject an entry
or envelope with a missing or non-SHA address. Addresses are deterministic for
the same canonical JSON content.

## 4. Accepted and review states

An accepted bundle is built only when the complete quality gate passes. A review
bundle can be written only with `allow_review=true` in the Python builder or
`--allow-review` on the CLI. Review opt-in does not rewrite the result state,
remove issue codes, or claim that the fixture passed.

The normal CI path does not pass the review flag. It builds the accepted
fixture and verifies the output address.

## 5. JSON projection

JSON is the canonical inspection projection. Keys are sorted by the CLI writer
and the document ends with one newline. The envelope retains arrays as arrays,
issue codes as arrays, and addresses as strings. Consumers should reject a
bundle with duplicate `record_id` values or a context different from the
envelope context.

Example compact entry:

```json
{
  "entry_id": "entry:...",
  "record_id": "positive-region-branching",
  "operation": "region_lineage",
  "fixture_state": "accepted",
  "result_state": "supported",
  "issue_codes": [],
  "source_ids": ["gdc-biospecimen-data", "gdc-biospecimen-submission"],
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "record_address": "sha256:...",
  "result_address": "sha256:..."
}
```

## 6. CSV projection

CSV uses one row per entry and this exact header order:

```text
entry_id,record_id,operation,fixture_state,result_state,issue_codes,source_ids,context_key,record_address,result_address
```

`issue_codes` and `source_ids` are pipe-separated within their cells. Empty
issue codes are represented by an empty cell. The CSV does not duplicate the
envelope metadata on every row; consumers should retain the JSON envelope when
they need quality and lineage addresses.

## 7. Markdown projection

Markdown is a human review projection. It contains the bundle ID, fixture ID,
state, context, entry count, quality address, lineage address, and a table with
record, operation, fixture state, result state, and issue codes. It is not the
canonical machine-readable form and must not be used to reconstruct payloads.

## 8. Verification procedure

`SpecimenLineageEvidenceBundleBuilder.verify` performs these checks:

1. recompute the envelope address;
2. require exactly twelve entries for the checked-in release fixture;
3. require SHA-256 record and result addresses;
4. require every entry context to equal the envelope context; and
5. reject an address-drifted envelope.

The quality gate separately verifies that entry identities match the evaluator
receipts, so `verify` is intentionally small and deterministic. A downstream
release process should run both the quality gate and bundle verification.

## 9. Lineage relationship

The bundle's `lineage_address` identifies a graph with four source nodes, one
fixture node, twelve record nodes, and twelve result nodes. The graph is a
receipt index, not a copy of the input. `declares` connects public receipts to
the fixture, `contains` connects the fixture to records, and `produces` connects
records to sanitized results.

## 10. Runtime relationship

The bundle is a batch evidence projection. The runtime is a four-stage
operational projection. The runtime's stage receipts use the same context and
source IDs but are addressed independently. A published runtime manifest does
not replace the batch quality gate; it demonstrates that the four operations
can be executed in a fixed order with conserved counts.

## 11. CLI examples

```powershell
python -m glio_noncode build-specimen-lineage-bundle examples/specimen-lineage-public-aggregate.json --output lineage-bundle.json
python -m glio_noncode build-specimen-lineage-bundle examples/specimen-lineage-public-aggregate.json --output lineage-bundle.csv --format csv
python -m glio_noncode build-specimen-lineage-bundle examples/specimen-lineage-public-aggregate.json --output lineage-bundle.md --format markdown
python -m glio_noncode build-specimen-lineage-bundle examples/specimen-lineage-public-aggregate.json --output review-bundle.json --allow-review
```

The last command is intended for inspection of a deliberately failing or
review-state fixture. It should not be used to make a failed gate appear
accepted.

## 12. Compatibility and change rules

The schema version changes when envelope semantics or required entry fields
change. Adding an optional display field can remain within the version only if
it does not copy raw payload, alter address inputs, or change the meaning of
state. Any change to address inputs, issue-code representation, context, or
source identity requires a new fixture address and a coordinated test update.

The compact bundle deliberately favors auditability over convenience. A caller
that needs raw observations must use the source fixture under its own access
policy; the release bundle is not a substitute for that boundary.
