# D04 data contract and fixture guide

## Fixture envelope

The public aggregate JSON has this top-level shape:

```json
{
  "fixture_id": "glio-noncode-reference-architecture-public-aggregate-v1",
  "version": "2026.08.reference-architecture.v1",
  "boundary": "public_aggregate_reference_context_and_release",
  "context_key": "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline",
  "sources": [],
  "operations": [],
  "cases": [],
  "content_address": "sha256:..."
}
```

The fixture loader rejects missing identifiers, unknown enum values, incorrect cardinality, duplicate case IDs, and addresses that do not use the `sha256:` prefix. The case count is derived from 16 operations multiplied by four scenarios per operation.

## Source record

Each source record carries:

| Field | Meaning |
| --- | --- |
| `source_id` | stable fixture-local join key |
| `title` | public source title |
| `uri` | public documentation or data page |
| `version` | source release or page boundary |
| `scope` | required to be `public_aggregate` |
| `license` | human-readable use boundary |
| `public_aggregate` | explicit public aggregate marker; must be `true` |
| `content_address` | source receipt address |

The source floor is 12; the checked-in fixture carries 20 sources spanning assembly, chain format, pangenome, transcript catalogs, ontologies, nomenclature, frequencies, and license references. Source records are receipts, not copies of upstream datasets.

## Operation record

Each operation specification carries an ordered identity and join contract:

```text
operation_id
capability_id
ordinal
operation
family
plane
input_contract
output_contract
dependencies
source_ids
control_policy
content_address
```

Operations are ordered from coordinate foundations through annotation and governance into release checks. Dependencies must point to earlier nodes. Source IDs must resolve to the fixture source table.

## Case record

Each case is a complete expected-outcome contract:

```text
case_id
operation_id
capability_id
operation
scenario
context_key
delegate_context_key
source_ids
payload
expected_state
expected_result_state
expected_issue_codes
expected_counts
description
content_address
```

Positive cases use the exact D04 context and delegate to the typed family adapters. Control cases preserve the same operation join but use one of the explicit control scenarios. Foreign-context controls use the GRCh37 context; malformed and identity controls retain the D04 context so the boundary can distinguish scope from payload and identity policy.

## Payload discipline

Payloads are aggregate-only. They can carry release labels, assembly labels, bounded counts, catalog classes, mapping statuses, and public reference descriptors. They cannot carry direct subject identifiers, medical record references, contact fields, or individual-level observations. The public-data audit walks nested mappings and lists to check the forbidden field set.

The fixture does not claim that a public catalog row is clinical evidence. It records the public reference mechanics necessary for reproducible normalization and release composition.

## Expected outcomes

Positive expected result states are the state returned by the delegated family fixture. Accepted aggregate state is permitted when the family returns `supported`, `accepted`, or `published`. Informative issue codes from a successful family operation are expected and compared exactly.

Controls have fixed results:

| Scenario | Expected result | Expected issue |
| --- | --- | --- |
| `foreign_context` | `out_of_domain` | `context_mismatch` |
| `malformed_input` | `invalid` | `malformed_input` |
| `identity_conflict` | `contradictory` | `identity_conflict` |

The policy module makes the same decision before any positive adapter dispatch. The operation module repeats the control decision at execution time so direct case execution cannot bypass the boundary.

## Evaluation contract

The evaluation has one receipt per case and ten global checks. Each case contributes checks for state, result, issue codes, bounded counts, output addressing, sanitized summary, and delegated context. The expected 458 checks are:

```text
64 cases × 7 case checks = 448
10 global closure checks = 10
total = 458
```

The evaluation is accepted only when every receipt and every check passes. A control receipt passes when its held state and declared issue match exactly; the control remains a review item after evaluation.

## Metrics

The metrics projection intentionally separates positive and control issue counts. Coordinate positives can retain informative issue codes, while every control contributes one policy issue. The default fixture therefore reports:

```text
source_count = 20
operation_count = 16
case_count = 64
evaluation_check_count = 458
result_state_count = 6
positive_count = 16
control_count = 48
control_issue_count = 48
validation_cell_count = 80
```

The aggregate issue count is not used as a failure threshold; receipt closure and the control-specific count are the meaningful gates.

## Schema projection

The schema manifest requires eight fixture fields, eight source fields, at least fourteen case fields, and eight receipt fields. Receipt fields intentionally omit raw payload. `reference_architecture_schema()` returns the required field tuples and its own content address.

## Canonicalization and replay

`reference_architecture_fixture_json()` serializes the fixture with stable indentation and sorted keys. `normalize_reference_architecture_mapping()` converts a mapping to a stable projection. `strip_reference_architecture_payloads()` removes payloads from a projection for safe receipt and review views without mutating the source fixture.

Replay executes the same fixture twice, compares receipt projections, compares check projections, and compares evaluation addresses. Release requires all three comparisons to match.

## Fixture maintenance

When adding an operation, update the operation enum, operation specification, positive payload mapping, four cases, source joins, plan dependencies, validation plane mapping, focused tests, documentation, CLI help, and CI invocation. Maintain four cases per operation and keep the case content address synchronized.

When changing a public source boundary, update the source record, license description, data audit expectation, release documentation, and relevant positive payload. Do not broaden the fixture to accept direct identity or individual-level fields.
