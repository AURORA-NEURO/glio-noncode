# Structural evidence bundle format

`StructuralEvidenceBundle` is the compact publication projection for the
Domain 02 C01-C04 evidence gate. It is designed for review, replay, and
artifact exchange. It is not a raw structural-variant archive.

## Root schema

The JSON root has these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `bundle_id` | string | caller-selected or fixture-derived bundle identity |
| `fixture_id` | string | source fixture identity |
| `fixture_version` | string | fixture schema version |
| `context_key` | string | exact six-field research context |
| `source_ids` | array[string] | sorted source receipt IDs |
| `entries` | array[object] | sorted positive and review summaries |
| `component_summaries` | object | fixture, scenario, quality, and lineage counts |
| `contract_manifest` | object | four operation contracts and address |
| `quality_summary` | object | gate state, failed IDs, quality address, and lineage address |
| `lineage_address` | string | sanitized source-to-result graph address |
| `content_address` | string | SHA-256 over the canonical body |
| `state` | string | `accepted` or `review` |

The builder also adds convenience fields when serializing:
`accepted`, `entry_count`, `positive_entry_count`, and `review_entry_count`.
These fields are removed before offline address verification, so they cannot
alter the canonical body hash.

## Entry schema

Every entry contains:

| Field | Type | Constraint |
| --- | --- | --- |
| `entry_id` | string | `positive:` or `review:` prefix plus record ID |
| `entry_class` | string | `positive` or `review` |
| `capability_id` | string | one of GNC-D02-C01 through C04 |
| `operation` | string | reconstruction, consensus, complex_resolution, or copy_number |
| `state` | string | observed fixture operation state |
| `result_state` | string | observed domain state |
| `structural_identifier` | string | fixture record ID, not a participant ID |
| `source_id` | string | source receipt identity |
| `evidence_address` | string | operation result address |
| `summary` | string | bounded human-readable operation detail |

Entries are sorted by entry class, capability ID, and entry ID. This ordering
is stable across Python versions and output formats. A bundle has twelve
entries for the canonical fixture: four positives and eight review controls.

## Component summaries

`component_summaries.fixture` contains:

- `check_count`;
- `passed_count`;
- `positive_count`; and
- `review_control_count`.

`component_summaries.scenarios` contains:

- `scenario_count`;
- positive and review counts; and
- the independent scenario pass state.

`component_summaries.quality` contains the number of quality assertions, the
number passed, and the quality gate state. These counts are summaries only;
the operation receipts and quality address remain the authoritative evidence
links.

`component_summaries.lineage` contains `node_count`, `edge_count`, `state`, and
`content_address`. For the canonical fixture the counts are 29 and 36. The
lineage component is a graph receipt, not an inline copy of the structural
payload. Its address is repeated at the root as `lineage_address` and inside
`quality_summary.lineage_address` so a consumer can compare all three without
loading the graph.

## Contract manifest

The contract manifest declares four records. Each contract binds:

- contract ID;
- capability ID;
- operation;
- required input fields;
- output fields;
- required provenance fields;
- accepted domain result states;
- review domain result states; and
- safety notes.

The contract manifest itself has a schema version, contract count, sorted
contract list, and content address. A consumer can reject an unfamiliar
contract version rather than parsing a partial projection.

## Quality summary

The quality summary contains:

```json
{
  "state": "accepted",
  "passed": true,
  "check_count": 17,
  "failed_check_ids": [],
  "evidence_boundary": "public aggregate structural observations; ...",
  "quality_address": "sha256:..."
}
```

`evidence_boundary` is a scope statement. It is not an empirical confidence
score. `quality_address` points to the full quality result, which is available
from the CLI before compaction.

## Address construction

The bundle body used for hashing is:

```text
bundle_id
fixture_id
fixture_version
context_key
source_ids
entries
component_summaries
contract_manifest
quality_summary
lineage_address
state
```

The body is canonicalized by the repository serialization layer. Mapping keys
are ordered, tuples become arrays, enums become values, and the SHA-256 digest
is prefixed with `sha256:`. The builder does not include convenience counts in
the body. A consumer must remove `content_address`, convenience fields, and
only those fields before recomputing the address.

## JSON projection

JSON is the lossless compact projection. It preserves nested contract and
quality summaries. The CLI chooses JSON for `.json` and for an explicit
`--format json`.

```powershell
python -m glio_noncode build-structural-bundle examples/structural-public-aggregate.json --output structural-bundle.json --format json
```

The command exits zero only when the bundle state is accepted. A review bundle
can be emitted with `--allow-review`; the JSON state remains `review` and the
exit code remains two.

## CSV projection

CSV contains only entry rows. The header is:

```text
entry_id,entry_class,capability_id,operation,state,result_state,structural_identifier,source_id,evidence_address,summary
```

It is intended for table review and simple downstream import. Contract and
quality summaries are not repeated on every row; consumers should retain the
JSON manifest alongside the CSV if they need the full evidence graph.

```powershell
python -m glio_noncode build-structural-bundle examples/structural-public-aggregate.json --output structural-bundle.csv --format csv
```

CSV uses UTF-8, a single header, comma quoting supplied by the standard writer,
and LF line endings. Entry order is the same as JSON order.

## Markdown projection

Markdown includes bundle identity, context, state, address, an entry table,
the evidence boundary, and source IDs. It is suitable for a review packet
where the compact table is more useful than nested JSON.

```powershell
python -m glio_noncode build-structural-bundle examples/structural-public-aggregate.json --output structural-bundle.md --format markdown
```

Markdown does not inline raw caller text or raw event records. The evidence
address on every row allows a reviewer to retrieve the detailed operation
report from the original local run.

## Review entries

Review entries are first-class rows. They include missing-mate, non-reciprocal
mate, malformed caller, disagreement, no-breakpoint, invalid-event, invalid
coordinate, and negative-copy-number controls in the canonical fixture.

The bundle never drops a control merely because the control passed through a
failure branch. A review row proves that the branch was executed and that the
declared issue remained visible. A review row is not an accepted scientific
result.

## Raw payload boundary

The builder receives the full fixture and full operation reports internally,
but the bundle entry contains only:

- the record identity;
- operation and capability;
- observed state;
- observed result state;
- source ID;
- operation content address; and
- a bounded summary.

The bundle does not copy `records`, caller `text`, breakend ALT strings,
haplotype segment payloads, or arbitrary attributes. A metadata review should
therefore inspect the quality report and source fixture separately when full
provenance is required.

## Verification algorithm

Offline verification follows these steps:

1. Parse the JSON root as an object.
2. Require a `content_address` beginning with `sha256:`.
3. Copy the root object.
4. Remove `content_address`, `accepted`, `entry_count`,
   `positive_entry_count`, and `review_entry_count`.
5. Canonicalize the remaining body with the repository serializer.
6. Compare the recomputed address with the declared address.

`StructuralEvidenceBundleBuilder.verify` returns a boolean and does not trust
the serialized `accepted` convenience field. A valid address does not itself
mean that the quality gate passed; consumers must inspect `state` and
`quality_summary.passed` as well.

## Pipeline manifest versus evidence bundle

The C01-C04 batch pipeline produces a manifest receipt with stage addresses.
The structural evidence bundle produces twelve entry summaries from the
fixture gate. They are related but not interchangeable:

- the pipeline manifest describes one request through four ordered stages;
- the evidence bundle describes four positive operation records and eight
  review controls;
- both omit raw payloads from their compact receipts; and
- both are content-addressed.

Use `run-structural-pipeline` for one batch boundary. Use
`build-structural-bundle` for a review packet covering positive and negative
evidence. Use `structural-lineage` when the reviewer needs a source-to-result
graph without raw operation payloads.

## Compatibility rules

A consumer should:

- reject an unknown `fixture_version` or contract schema version;
- require the exact context key expected by the consuming case;
- treat `ambiguous` as a domain state requiring review, not as supported truth;
- preserve every source ID and evidence address;
- keep review entries when converting to another format; and
- avoid using entry counts as a substitute for the quality report.

If a future format adds a field, it must not change the interpretation of the
existing address body without a schema-version change. If a future format
removes a field, it must provide a migration that retains source and operation
addresses.

## Limitations

This format is a review and replay artifact. It does not store raw reads,
alignment evidence, caller calibration, clinical assertions, or specimen
consent. It cannot establish that a complex path is biologically correct, that
a copy-number median is a true state, or that a public source is appropriate
for a specific institution. Those decisions require additional evidence and
review outside this compact bundle.
