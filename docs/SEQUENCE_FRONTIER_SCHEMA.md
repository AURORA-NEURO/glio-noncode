# Sequence frontier schema

## Common receipt fields

Every C13-C16 receipt carries these common fields:

| Field | Type | Constraint |
| --- | --- | --- |
| `record_id` | string | unique within the fixture |
| `operation` | enum | one of four declared operations |
| `role` | enum | `positive` or `control` |
| `context_key` | string | exact six-part context key |
| `source_ids` | tuple of strings | all resolve to source receipts |
| `adapter_state` | enum | operation state plus declared review states |
| `summary` | object | operation-specific fields only |
| `observed_issue_codes` | tuple of strings | bounded issue vocabulary |
| `content_address` | string | hash of receipt content |

The context key is serialized as
`reference|disease|age|cell_state|territory|treatment`. The checked-in value is
`GRCh38|diffuse_glioma|adult|stem_like|core|untreated`.

## Operation schemas

### C13 `enhancer_grammar`

Required summary fields are `state`, `motif_hit_count`, `compatible_pair_ids`,
`review_ids`, `coverage`, and `issue_codes`. Coverage is a descriptive fraction
over declared motif rules. A positive record must retain at least one compatible
pair and meet the configured coverage floor.

### C14 `allele_saturation`

Required summary fields are `state`, `point_count`, `positive_effect_ids`,
`review_ids`, `mean_delta`, and `issue_codes`. The schema allows review for
uncertainty above the floor or for an empty positive-effect set. Deltas retain
the declared reference and alternate points without claiming biological effect.

### C15 `ensemble_disagreement`

Required summary fields are `state`, `prediction_count`, `stable_ids`,
`review_ids`, `mean`, `disagreement`, and `issue_codes`. Stable prediction IDs
are required for every value. Missing predictions and disagreement above the
floor remain distinct review conditions.

### C16 `sequence_evidence_publish`

Required summary fields are `state`, `sequence_ids`, `records_address`,
`bundle_address`, `model_ids`, and `issue_codes`. A published record requires
non-empty sequence IDs, model IDs, record address, and bundle address. Empty
sequence records abstain; malformed publication metadata is invalid.

## Validation checks

The schema validator declares four schemas and emits 23 checks: two fixture-wide
checks and five checks per operation. It verifies record cardinality, operation
coverage, context preservation, declared states, declared output fields, bounded
issue codes, and prohibited-claim absence. The validator is intentionally
strict about output shape while allowing operation-specific review states.

The schema vocabulary is closed. Unknown issue codes, missing source receipts,
missing context, unrecognized states, and missing output fields fail validation.
Schema validation is independent from the quality gate so callers can inspect
shape failures before evaluating release readiness.

## Serialization restrictions

JSON output is canonicalized before content addressing. Exporters use the typed
review view and remove raw sequence fields, raw external payloads, subject
identifiers, and unsupported claim text. The schema records provenance and
uncertainty fields but does not permit clinical, causal, treatment, probability,
or calibration claims in operation summaries.
