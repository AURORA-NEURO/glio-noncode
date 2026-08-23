# Evidence release frontier data dictionary

| Field | Shape | Meaning |
| --- | --- | --- |
| `fixture_id` | string | stable public fixture identity |
| `fixture_version` | string | schema and contract version |
| `context_key` | string | exact ordered research boundary |
| `source_ids` | array of strings | joins to public source receipts |
| `payload` | object | operation input projection |
| `expected_state` | enum | fixture-declared control contract |
| `expected_issue_codes` | array of strings | expected negative-control reasons |
| `observed_state` | enum | operation result state |
| `issue_codes` | array of strings | normalized operation findings |
| `output` | object | safe operation projection |
| `content_address` | string | SHA-256 canonical-content receipt |
| `signature` | string | HMAC receipt for a dossier, never a key |

The registry, schema, fixture, execution, and check records all use the same
canonical serialization and address format. Timestamps are not used to establish
identity. A consumer can persist the JSON projection and replay it in a separate
process.

## Address rules

Addresses are computed from canonical JSON with sorted object keys and compact
separators. Dataclasses and enum values are converted to their JSON projection
before hashing. The address is an integrity receipt, not an access-control token and
not a statement that a source is true.

## Control vocabulary

`context_mismatch` means the row is outside the exact supported context and is
blocked. `score_below_threshold` means the proposed C13 transition is not closed.
`independent_reviewers_missing` and `independent_sources_missing` preserve missing
support as review. `supersession_target_missing`, `self_supersession`, and
`supersession_cycle` preserve graph defects. `required_section_missing`,
`duplicate_section_id`, and `item_address_missing` preserve bundle defects.
`dossier_expired` and `dossier_payload_empty` preserve publication defects.
`invalid_payload` and `schema_invalid` identify shape failures. `signature_mismatch`
identifies a verification failure and results in rejection.

## Export guarantees

The safe output projection contains public IDs, state, issue codes, counts, addresses,
and declared metadata. It removes fields whose names indicate private credentials or
individual-level identifiers. This projection is used by the evaluator, review
queue, CSV export, runtime trace, and public aggregate fixture checks.

## Consumer guidance

Consumers should treat unknown enum values as a compatibility failure, preserve
unrecognized fields when storing a raw JSON envelope, and never infer a positive
state from a missing `issue_codes` field. A row with no evidence address should not
be treated as a zero-evidence row; it should be repaired or held for review.
