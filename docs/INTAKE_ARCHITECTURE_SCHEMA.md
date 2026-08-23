# D01 schema and receipt model

The D01 schema is a closed, content-addressed projection. Every durable
receipt has an address formed from its canonical JSON projection. Runtime
timestamps from lower-level parser receipts are not used as the D01 replay
identity; stable input and output addresses are used instead.

## Fixture envelope

```json
{
  "fixture_id": "intake-architecture-d01",
  "version": "2026.08.intake-architecture.v1",
  "boundary": "public_aggregate_variant_identity_and_intake",
  "context_key": "GRCh38|glioma|adult|aggregate|public_reference|pre_treatment",
  "sources": [],
  "operations": [],
  "cases": [],
  "content_address": "intake-fixture:<digest>"
}
```

The fixture has six source receipts, sixteen operation specifications, and 64
cases. Each operation has four cases and each case has a source join, public
identifier, bounded payload, expected state, expected issue codes, and content
address.

## Public fields

| Field | Type | Required | Scope |
| --- | --- | :---: | --- |
| `fixture_id` | string | yes | public aggregate |
| `operation_id` | string | yes | public aggregate |
| `capability_id` | string | yes | public aggregate |
| `context_key` | string | yes | public aggregate |
| `source_ids` | array[string] | yes | public aggregate |
| `public_identifier` | string | yes | public aggregate |
| `payload` | object | yes | public aggregate |
| `expected_state` | enum | yes | public aggregate |
| `issue_codes` | array[string] | yes | public aggregate |
| `content_address` | string | yes | public aggregate |
| `rollback_version` | string | yes at release | public aggregate |

No subject, contact, or private identity field is part of this schema. The
aggregate sample and batch values in the executable fixture are non-subject
public receipt labels.

## State vocabulary

`accepted` means the declared contract and boundary checks passed. `review`
means a control, ambiguity, missing field, or source mismatch must remain held.
`blocked` is reserved for a release or policy hard stop. `abstained` means the
underlying primitive did not have a supported representation and did not
silently flatten the input.

## Addresses and replay

Addresses use a stable prefix plus digest. The fixture content address covers
sources, operations, and cases. Operation result addresses cover the sanitized
result projection and expected state. Primitive receipts are joined by address
only. A replay compares the evaluation address and every result projection;
different addresses are a failure even when the scalar state is unchanged.

## Validation matrix

The matrix is the Cartesian product of seven planes and sixteen operations:
112 cells. The planes are ingestion, parsing, normalization, identity, policy,
provenance, and release. A cell passes only if the positive operation result is
accepted with no issue code and retains an address.

## Offline artifacts

The bundle contains five artifacts:

- manifest;
- source receipts;
- operation results;
- review queue;
- hash-linked ledger.

Each artifact is marked offline-capable and has a digest and a receipt address.
The release stores all five artifact addresses and a rollback version.
