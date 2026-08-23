# Module fabric schema

Version: `2026.08.module-fabric.v1`

Boundary: `public_aggregate_module_integration`

## Fixture

| Field | Type | Required | Public | Invariant |
| --- | --- | ---: | ---: | --- |
| `fixture_id` | string | yes | yes | stable across replay |
| `fixture_version` | string | yes | yes | exact contract version |
| `context_key` | string | yes | yes | exact context is retained |
| `evidence_boundary` | enum | yes | yes | public aggregate only |
| `sources` | array | yes | yes | five HTTPS receipts |
| `records` | array | yes | yes | 32 rows, two per domain |
| `content_address` | SHA-256 | yes | yes | recomputed from canonical body |

## Source receipt

Source receipts must contain `source_id`, `title`, `uri`, `scope`, `version`,
and `content_address`. The URI must use HTTPS and `scope` must equal
`public_aggregate`. A receipt does not assert that the source is available at
runtime; it records the public citation boundary used by the fixture.

## Record

| Field | Type | Required | Invariant |
| --- | --- | ---: | --- |
| `record_id` | string | yes | unique within fixture |
| `domain_id` | `D01`–`D16` | yes | matches capability prefix |
| `capability_id` | catalog ID | yes | resolves in the 256-row catalog |
| `role` | `positive`/`control` | yes | controls cannot expect accepted |
| `context_key` | string | yes | record envelope uses exact fixture context |
| `source_ids` | array of strings | yes | every ID joins a known receipt |
| `payload` | object | yes | never copied to public output |
| `expected_state` | state enum | yes | positive expects accepted; control is held |
| `expected_issue_codes` | array of strings | yes | control issue floor |
| `notes` | string | yes | human-readable bounded rationale |
| `content_address` | SHA-256 | yes | hashes all record fields except address |

The positive payload declares owning domain, capability ID, capability order,
context, and reference floors. The control payload declares a foreign domain
and foreign context. The operation reads these fields only to check declared
ownership and boundaries.

## Execution

Execution output is a projection. It contains domain and capability identity,
role, context booleans, ledger state, issue count, reference counts, and
reference declaration strings. It does not contain the raw record payload or
imported Python objects.

Each implementation and test declaration gets a receipt with:

```text
reference
kind
module_name
symbol_name
state
detail
content_address
```

`state` is `resolved` or `failed`. Failure details are retained for repair and
are not converted to a negative scientific observation.

## Evaluation checks

Each of the 32 records receives eight checks:

1. expected versus observed state;
2. expected issue-code floor;
3. role boundary;
4. domain closure;
5. implementation reference resolution;
6. test-surface resolution;
7. public projection safety; and
8. execution content address.

The canonical fixture therefore produces 256 checks. The evaluation is
accepted only when every check passes.
