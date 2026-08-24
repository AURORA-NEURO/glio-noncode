# D12 Public Data Contract

The checked-in D12 fixture is a public aggregate research dataset designed for deterministic review and integration.

## Envelope

The root object contains:

- `fixture_id`: stable D12 aggregate identity.
- `version`: pinned D12 contract version.
- `boundary`: `public_aggregate_non_patient`.
- `context_key`: `multi_context_public_aggregate`.
- `foreign_context_key`: explicit foreign-context control label.
- `family_contexts`: exact context key for each of the four delegate families.
- `sources`: 22 prefixed source receipts.
- `operations`: 16 semantic operation specifications.
- `cases`: 64 positive and control cases.
- `content_address`: canonical envelope address.

## Sources and operations

Each source retains a D12 source identifier, family, source kind, source version, URI, family context, delegate source identifier, delegate fixture identifier, public aggregate flag, delegate content address, and D12 content address. Each operation retains its D12 capability identifier, semantic operation, delegate operation, family, plane, contracts, dependency list, source joins, control policy, and content address.

## Cases

Each case stores both the aggregate and delegate context, delegate fixture and record identity, positive or control class, prefixed source joins, and a bounded payload. The payload includes the public delegate input, evaluator output projection, output address, context, and fixture identity. Expected state and issue codes are copied from the family evaluator contract. Expected counts provide deterministic source, field, and row accounting.

## Validation

`validate_cohort_architecture_mapping` checks required fields, boundary, envelope context, four family contexts, 22/16/64 cardinalities, contiguous operation ordinals, and four cases per operation. `validate_cohort_architecture_fixture` checks typed identity, cardinality, source and operation joins, case balance, public source visibility, and complete family contexts. The data audit additionally checks four-family coverage, four scenarios per operation, public source flags, and content addresses.

The fixture is generated from the existing public aggregate family fixtures through `cohort_architecture_fixture_json`. It is checked in so replay, CLI use, and release review all consume the same deterministic data.
