# Domain 04 C13-C16 data dictionary

## Fixture envelope

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `fixture_id` | text | yes | Stable public aggregate identity. |
| `fixture_version` | text | yes | Version of the checked-in fixture contract. |
| `context_key` | text | yes | Exact assembly, disease, age, specimen, territory, and phase context. |
| `evidence_boundary` | text | yes | Must be `public_aggregate_non_patient`. |
| `sources` | list | yes | Five public source receipts. |
| `records` | list | yes | Sixteen executable operation records. |
| `content_address` | text | yes | Canonical address over the fixture envelope. |

The context key is
`GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline`. Context is
compared as an exact value. A record with a different assembly or phase is not
silently remapped.

## Source receipt

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id` | text | Stable source identity used by records. |
| `title` | text | Human-readable public source title. |
| `uri` | HTTP(S) text | Public source or documentation location. |
| `source_kind` | text | Reference sequence, annotation, population, or documentation family. |
| `release` | text | Declared source release or assembly label. |
| `accessed_on` | ISO date text | Date the receipt was assembled. |
| `license` | text | Declared source terms label. |
| `scope` | text | Narrow description of the retained source use. |
| `content_address` | text | Address over the receipt fields. |

The fixture uses HGNC, Ensembl, NCBI RefSeq, UCSC Genome Browser, and gnomAD
public source receipts. The package retains identity and scope; it does not
claim that a URI fetch was performed during a deterministic test.

## Operation record

| Field | Type | Meaning |
| --- | --- | --- |
| `record_id` | text | Unique positive or control record ID. |
| `operation` | enum | One of the four C13-C16 operation values. |
| `role` | enum | `positive` or `control`. |
| `context_key` | text | Exact context inherited by the operation. |
| `source_ids` | list[text] | Source receipts supporting the row. |
| `payload` | object | Aggregate operation input. |
| `expected_state` | text | Expected adapter state. |
| `expected_issue_codes` | list[text] | Expected retained issue vocabulary. |
| `description` | text | Boundary intent for the row. |
| `content_address` | text | Address over the record declaration. |

## Payload fields by operation

### C13 source provenance

`records` is a list of source rows. Each row can contain `source_id`,
`source_uri`, `declared_checksum`, `observed_checksum`, `license_id`, and
`context_key`. `require_checksum_match` defaults to true. A source is accepted
only when URI, declared checksum, license, observed match, and context all
pass.

### C14 annotation drift

`previous` and `current` are lists of annotation rows keyed by
`annotation_id`. `identity_field` defaults to `annotation_id`.
`ignored_fields` defaults to `retrieved_at` and `source_uri`.
`drift_threshold` defaults to `0.2` and is measured as changed fields divided
by comparable fields. A new identity is drift even when it has no previous
row.

### C15 reproducible reference bundle

`records` contains rows with `reference_id` or `dataset_id`, `status`,
`context_key`, source identity, URI, and checksum. `bundle_id` and
`schema_hash` are required. `require_available` defaults to true. Rows are
sorted by reference identity before `bundle_address` is calculated.

### C16 reference release gate

`release_id`, `bundle_address`, and `checks` are required. The default check
map has five keys: `checksum`, `schema`, `license`, `context`, and `source`.
`required_checks` can narrow or extend the set for an explicit test, but a
missing required key is false. `failed_checks` retains each failed name.

## State vocabulary

| State | Meaning |
| --- | --- |
| `accepted` | Provenance or stable annotation projection passed. |
| `review` | Provenance is incomplete or inconsistent. |
| `drift` | Annotation identity or substantive fields changed. |
| `published` | A reference bundle or release gate passed. |
| `blocked` | A required boundary failed and publication is prevented. |

The `accepted` Boolean on an execution is true only for `accepted` and
`published` states. A control may be structurally accepted when it demonstrates
that an ignored receipt field is harmless; its role remains `control`.

## Issue vocabulary

| Code | Operation | Meaning |
| --- | --- | --- |
| `missing_source_uri` | C13 | Source location is absent. |
| `missing_checksum` | C13 | Declared checksum is absent. |
| `missing_license` | C13 | License receipt is absent. |
| `checksum_unverified` | C13 | Observed checksum is absent or mismatched. |
| `provenance_context_mismatch` | C13 | Source context differs from the fixture context. |
| `bundle_context_mismatch` | C15 | Reference row context differs from the bundle context. |
| `bundle_unavailable` | C15 | Reference row status is not available, validated, or active. |
| `bundle_missing_reference_id` | C15 | Reference identity is missing. |
| `bundle_schema_missing` | C15 | Bundle schema address is missing. |
| `release_check_failed` | C16 | At least one required release check is false or absent. |

Issue codes are sorted before they are placed in a receipt. The contract
registry rejects undeclared codes in independent projection checks.

## Output redaction

Execution receipts may expose counts, IDs, state, field names, scores, issue
codes, and addresses. They do not expose raw operation rows. The bundle and
review view use the same rule. The data dictionary therefore describes input
payloads for reproducibility, while public output reports retain only the
bounded summary fields needed for review.
