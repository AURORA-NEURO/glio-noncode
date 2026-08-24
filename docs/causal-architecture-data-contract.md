# D11 Public Data Contract

The checked-in fixture is a public aggregate research dataset. It is designed for deterministic tests, review, and downstream integration, not for person-level analysis.

## Envelope

The root object contains:

- `fixture_id`: stable aggregate identity.
- `version`: D11 contract version.
- `boundary`: `public_aggregate_non_patient`.
- `context_key`: the pinned analysis context.
- `foreign_context_key`: the explicit context control.
- `sources`: 20 source receipts.
- `operations`: 16 ordered operation specifications.
- `cases`: 64 positive and control records.
- `content_address`: canonical envelope address.

## Source receipt

Each source has a D11 source identifier, family, source kind, source version, URI, context key, public aggregate flag, delegate source identifier, and content address. The delegate source is retained as provenance, while the D11 source identifier provides a stable aggregate join key.

## Operation specification

Each operation has an operation identifier such as `D11-C01`, capability identifier, ordinal, operation enum, family, plane, input and output contract names, dependency identifiers, source identifiers, control policy, and content address. The contract matrix requires four cases per operation in the order positive, control A, control B, and control C.

## Case record

Each case stores its operation and family joins, scenario, aggregate context, source identifiers, delegate fixture and record identifiers, delegate context, bounded delegate payload, expected aggregate state, expected delegate result state, expected issue codes, expected counts, description, and content address. The payload contains aggregate research fields only. The compliance gate rejects keys that would cross the public aggregate boundary.

## Validation and replay

`validate_causal_architecture_mapping` checks required fields, boundary, context, and cardinalities. `validate_causal_architecture_fixture` checks typed identity and source/operation joins. `audit_causal_architecture_data` performs source, operation, case, scenario, context, address, and boundary checks. Replay then compares the serialized evaluation and output addresses.

The data file is generated from the pinned public fixture through `causal_architecture_fixture_json`. It is not assembled from a prior repository or framework.
