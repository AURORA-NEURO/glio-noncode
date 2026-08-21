# Specimen frontier bundle format

The specimen frontier bundle is a compact, deterministic release receipt for
Domain 03 C01-C04 evidence runs. It is produced by
`SpecimenFrontierEvidenceBundleBuilder` and can be serialized as JSON, CSV, or
Markdown. The bundle deliberately contains summaries and addresses, not raw
payloads.

## 1. Bundle envelope

The JSON envelope has this shape:

```json
{
  "schema": "specimen-frontier-bundle-v1",
  "bundle_id": "specimen-frontier-c01-c04",
  "fixture_id": "specimen-frontier-public-aggregate-v1",
  "state": "accepted",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "source_ids": ["..."],
  "entry_count": 12,
  "entries": [],
  "lineage_address": "sha256:...",
  "quality_address": "sha256:...",
  "content_address": "sha256:..."
}
```

Fields are ordered in the serialized representation. Objects are sorted by
key for hashing and arrays are sorted only where the schema declares a set.
Record order is the fixture order, which preserves the review surface and
makes execution diffs easy to inspect.

The bundle state is one of:

| State | Meaning |
| --- | --- |
| `accepted` | all required checks pass and publication is allowed |
| `review` | evidence is present but one or more entries are review controls |
| `blocked` | a required boundary check failed |

An accepted build cannot be obtained by filtering out review entries. The
positive and control floors are computed before entry serialization.

## 2. Entry schema

Each entry represents one evaluated record:

| Field | Type | Description |
| --- | --- | --- |
| `entry_id` | string | stable bundle-local entry identity |
| `record_id` | string | fixture record key |
| `specimen_identifier` | string | aggregate specimen key used for display |
| `operation` | string | ontology, matched normal, purity/ploidy, or integrity |
| `fixture_state` | string | `accepted` or `review` |
| `result_state` | string | adapter state after execution |
| `issue_codes` | array | sorted structured issue identifiers |
| `source_ids` | array | receipt IDs supporting the record |
| `context_key` | string | exact six-field context key |
| `record_address` | string | source record content address |
| `result_address` | string | sanitized result content address |

The entry does not copy the operation payload. It also does not include
patient-level names, direct identifiers, raw genotype strings, or unbounded
source text. A recursive sensitive-key scan runs before serialization.

## 3. Addressing rules

The following values are content addressed independently:

1. each fixture record;
2. each adapter result summary;
3. the evaluation receipt;
4. the quality report;
5. the lineage graph;
6. the final bundle.

Addresses use a `sha256:` prefix followed by a lowercase hexadecimal digest.
The digest input is canonical JSON with compact separators and sorted object
keys. The content-address field is excluded from the value that it addresses.

For a record, the address input includes record ID, source IDs, context,
operation, fixture state, payload, and expected result. For a bundle, the
address input includes the envelope fields, entry addresses, quality address,
lineage address, and state.

An address is not a signature and does not prove who produced a file. It is a
deterministic equality check for local and CI replay.

## 4. JSON serialization

JSON output is intended for machines and review tooling. The builder emits a
single object with no trailing data. The required top-level fields are:

```text
schema
bundle_id
fixture_id
state
context_key
source_ids
entry_count
entries
quality_address
lineage_address
content_address
```

`entry_count` must equal the number of entries. `source_ids` is the sorted
union of entry source IDs. Every entry context must equal the envelope context.
The verifier recomputes all record, quality, lineage, and bundle addresses.

A JSON bundle is written with:

```powershell
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-public-aggregate.json --output specimen-bundle.json --format json
```

## 5. CSV serialization

CSV is a flat review projection. The header is:

```text
entry_id,record_id,specimen_identifier,operation,fixture_state,result_state,issue_codes,source_ids,context_key,record_address,result_address
```

Array-valued fields are joined using a semicolon. The context key is retained
as one quoted field because it contains separators. CSV does not carry the
quality or lineage graph body; those are represented by the companion JSON
receipt fields in the bundle directory or by the bundle address.

CSV values are escaped using the standard CSV writer. Consumers must not split
on commas without honoring quoting rules. Entry order matches the JSON entry
order.

Create a CSV projection with:

```powershell
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-public-aggregate.json --output specimen-bundle.csv --format csv
```

## 6. Markdown serialization

Markdown is for human review. It contains:

- the bundle identity and state;
- exact context and source IDs;
- quality and lineage addresses;
- the entry count;
- one table row per sanitized entry;
- issue codes in a bounded text column.

The Markdown projection is not a replacement for the JSON receipt. Its table
is a view and can be reformatted without changing the addressed JSON bundle.

Create it with:

```powershell
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-public-aggregate.json --output specimen-bundle.md --format markdown
```

## 7. Quality receipt

The quality receipt is referenced by `quality_address`. Its summary includes:

```json
{
  "passed": true,
  "check_count": 21,
  "failed_check_ids": [],
  "positive_count": 4,
  "control_count": 8,
  "operation_count": 4
}
```

The 21 checks include fixture identity, aggregate scope, source agreement,
context agreement, address floors, replay, scenario coverage, contract state
coverage, sanitized output, receipt identity, issue-control coverage, and
lineage shape. A failed check carries an ID and reason in the full quality
report.

## 8. Lineage receipt

The lineage graph is a separate addressed object. Its node schema is:

| Node kind | Required identity | Address source |
| --- | --- | --- |
| `source` | source ID and URL | source receipt |
| `fixture` | fixture ID and context | fixture catalog |
| `record` | record ID and operation | record address |
| `result` | record ID and result state | result address |

Edges have `edge_id`, `source_id`, `target_id`, and `relation`. Valid relation
values are `declares`, `contains`, and `produces`. The canonical graph has:

```text
4 source nodes
1 fixture node
12 record nodes
12 result nodes
36 typed edges
```

The graph is a run provenance graph. It does not represent tumor evolution,
clonal ancestry, or a biological parent relationship.

## 9. Runtime receipt

The pipeline runtime emits one receipt per stage and a final manifest:

```json
{
  "stage": "purity_ploidy",
  "state": "accepted",
  "input_count": 1,
  "accepted_count": 1,
  "review_count": 0,
  "blocked_count": 0,
  "issue_codes": [],
  "content_address": "sha256:..."
}
```

The stage order is fixed:

```text
ontology_mapping
matched_normal
purity_ploidy
sample_integrity
```

Counts are conserved between stages. A stage can move a record from accepted
to review or blocked, but no stage may make a record disappear. The final
manifest lists sanitized record IDs and states; it does not copy raw payloads.

## 10. Verification behavior

`SpecimenFrontierEvidenceBundleBuilder.verify` checks:

- schema and state vocabulary;
- fixture and bundle identity;
- exact context;
- source membership and deterministic order;
- entry count and unique entry IDs;
- record and result address formats;
- quality and lineage address formats;
- sensitive-key absence;
- content-address equality.

The verifier is strict about missing fields and mismatches. It does not repair,
sort, or rewrite a bundle during verification. A caller that wants a new
ordering must build a new bundle and accept its new content address.

## 11. Review and publication policy

The builder refuses to publish review-state data as accepted. To create a
review bundle for inspection, callers must pass an explicit opt-in:

```powershell
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-pipeline-review.json --output review-bundle.json --allow-review
```

The aggregate public fixture has review controls by design, so an accepted
bundle is assembled from its evaluated evidence entries while preserving each
entry's fixture state. The pipeline command has a separate accepted example
for release-path testing and a review example for state propagation testing.

Publication means only that the local evidence bundle passed its declared
mechanical checks. It does not mean that a specimen relationship, purity
estimate, ploidy estimate, contamination call, or swap decision is medically
validated.

## 12. Versioning and compatibility

The schema identifier is `specimen-frontier-bundle-v1`. A backwards-compatible
field addition requires a new verifier test and a documented optional-field
rule. A change to address inputs, entry ordering, state vocabulary, or required
fields requires a new schema identifier.

Consumers should check the schema before parsing. Unknown fields may be
retained by a forward-compatible consumer, but required fields must not be
invented. A consumer that cannot validate the content address should report
the bundle as unverified rather than treating it as accepted.

## 13. Command examples

Build all supported projections:

```powershell
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-public-aggregate.json --output specimen-bundle.json --format json
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-public-aggregate.json --output specimen-bundle.csv --format csv
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-public-aggregate.json --output specimen-bundle.md --format markdown
```

Inspect the related receipts:

```powershell
python -m glio_noncode specimen-frontier-quality-gate examples/specimen-frontier-public-aggregate.json --output specimen-quality.json
python -m glio_noncode specimen-frontier-lineage examples/specimen-frontier-public-aggregate.json --output specimen-lineage.json
python -m glio_noncode specimen-frontier-contracts --output specimen-contracts.json
```

The repository tests exercise every projection, address verifier, state
transition, line-count floor, and CLI path. The CI workflow runs JSON output
for the release path and keeps CSV and Markdown covered by the unit tests.
