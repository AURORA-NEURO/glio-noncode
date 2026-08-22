# Chromatin frontier schema

## Common receipt fields

Every C13-C16 execution receipt contains:

| Field | Type | Constraint |
| --- | --- | --- |
| `record_id` | string | unique fixture record ID |
| `operation` | enum | one of four declared operations |
| `role` | enum | `positive` or `control` |
| `context_key` | string | exact fixture context |
| `expected_state` | string | fixture expectation |
| `adapter_state` | string | supported or declared review state |
| `primary_count` | integer | operation input count |
| `secondary_count` | integer | operation output count |
| `observed_issue_codes` | tuple | closed issue vocabulary |
| `summary` | object | operation-specific sanitized fields |
| `content_address` | string | receipt hash |

The serialized context is
`reference|disease|age|cell_state|territory|treatment`. The fixture value is
`GRCh38|glioma|adult|stem_like|tumor|unknown`.

## Operation summaries

### C13 `chromatin_segmentation`

The summary requires `state`, `observation_count`, `segment_count`,
`ambiguous_segment_ids`, `state_labels`, and `issue_codes`. It exposes interval
support and labels without exposing raw rows.

### C14 `allele_specific_chromatin`

The summary requires `state`, `variant_ids`, `result_count`, `directions`,
`median_deltas`, and `issue_codes`. Deltas are retained as descriptive
comparisons with replicate ambiguity visible.

### C15 `epigenomic_purity`

The summary requires `state`, `marker_count`, `estimate_count`,
`aggregate_purity`, `purity_spread`, `estimate_states`, and `issue_codes`.
Null aggregate and spread values are valid when a denominator is unavailable.

### C16 `batch_composition_correction`

The summary requires `state`, `observation_count`, `correction_count`,
`corrected_feature_ids`, `corrected_signals`, and `issue_codes`. Adjustment
terms remain available in the typed adapter object and are not replaced by a
single unexplained value.

## Validation

The schema validator declares four schemas and emits 23 checks: three fixture
checks and five checks per operation. It verifies schema cardinality, operation
coverage, context preservation, record cardinality, allowed states, output
fields, issue vocabulary, and prohibited-claim absence. Unknown issue codes or
missing summary fields fail independently of the quality gate.

## Serialization restrictions

Canonical JSON is content-addressed. Exporters remove raw input text, subject
identifiers, and unsupported claims. The schema records uncertainty, source
context, and review states but does not permit causal, clinical, truth-label, or
treatment conclusions in operation summaries.
