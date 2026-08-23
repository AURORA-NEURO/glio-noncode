# Workbench release frontier schema

Fixture version: `2026.08.d15-c13-c16.v1`.

Supported context:

`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment`

The public fixture contains five HTTPS source receipts and sixteen records. Each
operation has one positive path and three controls. Each row carries capability,
operation, role, context, source IDs, payload, expected state, expected issue codes,
notes, and a SHA-256 address.

## Required fields

Review forms require `form_id`, `reviewer_id`, `context_key`, `schema`, and
`response`. Report exports require `report_id`, `context_key`, `format`, and
`sections`. Search requires `query`, `context_key`, `records`, and `commands`.
Accessibility requires `surface_id`, `context_key`, `surface`, and
`required_criteria`.

## State semantics

`reviewed` means all required form fields are valid. `exported` means a non-empty,
unique section manifest was rendered in a supported format. `searched` means a
deterministic result set or command match exists. `passed` means all declared
accessibility criteria pass. `review` preserves an incomplete, empty, failed, or
no-match boundary. `blocked` quarantines foreign context. `rejected` preserves
malformed identity or schema input.

## Content addressing

The canonical serialization utility sorts object keys and encodes enums by value.
Inputs and outputs are addressed with SHA-256. Addresses are integrity receipts;
they are not permissions, user identities, or truth scores.
