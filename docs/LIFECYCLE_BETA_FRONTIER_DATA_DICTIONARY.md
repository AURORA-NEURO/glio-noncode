# Lifecycle Beta Frontier Data Dictionary

The C05-C12 schema is lifecycle-beta-frontier-schema, version 2026.08.v1.
All records are public aggregate research data with exact context and
content-addressed receipts.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| record_id | string | yes | Stable operation/role row identifier |
| operation | enum | yes | One of the eight C05-C12 operation values |
| role | enum | yes | positive or control |
| context_key | string | yes | Exact assembly, disease, age, state, territory, and treatment context |
| source_ids | array | yes | Public source receipts bound to the row |
| payload | object | yes | Operation-specific aggregate input |
| expected_state | enum | yes | Fixture boundary expected from the adapter |
| expected_issue_codes | array | yes | Explicit unresolved/control vocabulary |
| notes | string | yes | Human-readable boundary rationale |
| content_address | SHA-256 | yes | Immutable row receipt |

## Operation values

| Operation | Capability | Primary output |
| --- | --- | --- |
| tier_adjudication | C05 | Direction-preserving tier result |
| provenance_lineage | C06 | Parent/supersession lineage view |
| uncertainty_ledger | C07 | Dimension-labeled uncertainty ledger |
| review_routing | C08 | Priority and role assignments |
| blinded_adjudication | C09 | Masked case decision result |
| comment_change_log | C10 | Append-only review log |
| release_decision | C11 | Research-only gate record |
| evidence_delta | C12 | Before/after evidence delta |

## State vocabulary

supported, review_required, partial, contradictory, out_of_domain,
abstained, ready_for_review, adjudicated, split_decision, approved,
conditional, and rejected remain separate. The state is descriptive and does
not establish scientific validity, reliability, causality, or clinical utility.

## Source boundary

The fixture has nine HTTPS receipts. The URIs are public aggregate receipt
addresses and do not represent patient-level retrieval. Source IDs are
retained on rows and in the lineage graph. A missing source, foreign context,
invalid field, or duplicate identity is a visible control state.
