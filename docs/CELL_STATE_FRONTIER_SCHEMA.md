# Domain 08 C13-C16 schema

The cell-state frontier schema is a typed output boundary. Each operation has a
common context/source/issue envelope and operation-specific summary fields.
Schema validation checks record counts, allowed states, required output fields,
issue vocabulary, and prohibited claim vocabulary.

## Common receipt envelope

Every execution receipt has:

| Field | Type | Rule |
| --- | --- | --- |
| `record_id` | string | unique within fixture |
| `operation` | enum | one of four Domain 08 operations |
| `role` | enum | `positive` or `control` |
| `context_key` | string | exact fixture context |
| `expected_state` | string | fixture expectation |
| `adapter_state` | string | observed bounded state |
| `primary_count` | integer | operation-specific row count |
| `secondary_count` | integer | operation-specific accepted count |
| `observed_issue_codes` | list[string] | bounded issue vocabulary |
| `summary` | object | sanitized operation output |
| `content_address` | string | SHA-256 content address |

The receipt never includes a raw input field inside the summary. The fixture
payload is used to run the adapter but is not copied into the evidence output.

## C13 schema

Schema ID: `GNC-D08-C13-schema-v1`

| Field | Type | Meaning |
| --- | --- | --- |
| `state` | state | supported or review outcome |
| `estimate_count` | integer | number of parsed estimates |
| `stable_ids` | list[string] | estimates passing the adapter gate |
| `review_ids` | list[string] | estimates requiring review |
| `abundances` | list[float] | bounded aggregate proportions |
| `intervals` | list[list[float]] | lower and upper endpoints |
| `issue_codes` | list[string] | invalid or scope findings |

Allowed review states are `partial`, `out_of_domain`, `abstained`, and
`invalid`. The schema rejects clinical, diagnostic, and truth claims.

## C14 schema

Schema ID: `GNC-D08-C14-schema-v1`

| Field | Type | Meaning |
| --- | --- | --- |
| `state` | state | supported or review outcome |
| `mapping_count` | integer | number of mapping rows |
| `mapped_ids` | list[string] | rows passing score and margin gates |
| `review_ids` | list[string] | rows held for review |
| `reference_state_ids` | list[string or null] | selected reference candidates |
| `margins` | list[float] | top-minus-second score margins |
| `issue_codes` | list[string] | ambiguity or scope findings |

The score margin remains descriptive. The schema rejects clinical, diagnostic,
and identity-truth claims.

## C15 schema

Schema ID: `GNC-D08-C15-schema-v1`

| Field | Type | Meaning |
| --- | --- | --- |
| `state` | state | supported or review outcome |
| `finding_count` | integer | number of OOD findings |
| `in_domain_ids` | list[string] | rows inside declared support |
| `ood_ids` | list[string] | rows outside declared support |
| `review_ids` | list[string] | rows requiring review |
| `distances` | list[float] | reference distances |
| `support_scores` | list[float] | support scores |
| `issue_codes` | list[string] | OOD, invalid, or scope findings |

The output is a support-boundary observation. It is not a diagnosis, clinical
classification, or territory truth claim.

## C16 schema

Schema ID: `GNC-D08-C16-schema-v1`

| Field | Type | Meaning |
| --- | --- | --- |
| `state` | state | supported or review outcome |
| `cell_count` | integer | number of aggregate cell IDs |
| `receipt_count` | integer | upstream mapping/abundance/OOD terms |
| `envelope_address` | string or null | published envelope address |
| `issue_codes` | list[string] | missing, invalid, or scope findings |

An accepted C16 summary has three upstream receipt terms and a non-null envelope
address. Review summaries retain a null address rather than creating a partial
release artifact that looks published.

## Issue vocabulary

The declared issue set is:

```text
context_mismatch
invalid_cell_count
invalid_interval_multiplier
ambiguous_reference_mapping
no_reference_scores
cell_state_out_of_domain
invalid_cell_state_row
empty_cell_ids
missing_receipt_address
```

Unknown issue codes fail schema validation. This prevents a new adapter branch
from silently introducing an unreviewed state vocabulary.

## Addressing and serialization

Schema manifests, checks, receipts, metrics, bundles, traces, and release
manifests carry SHA-256 content addresses. Addresses are computed from the
semantic body before the address field is added. Re-running the same fixture
therefore produces the same receipt, metric, and bundle addresses.

The JSON export uses sorted keys and indentation for stable review diffs. CSV
exports expose one row per receipt, review row, or operation metric. Markdown
exports are intended for human inspection and preserve the same state and
priority boundaries as the structured view.
