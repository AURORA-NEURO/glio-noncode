# Module-fabric operation ledger

The module-fabric operation ledger is the operational reconciliation layer for
the repository-wide aggregate integration surface. It records ordered stage
receipts, counts, states, and content addresses. It does not copy fixture
payloads, private subject keys, or unbounded source responses into a run log.

## Scope

The ledger is intentionally bound to the public aggregate boundary:

- the canonical fixture contains 32 rows, with one positive row and one held
  control row for each of the 16 domains;
- the runtime contains 20 ordered stages;
- every stage carries the same 32-record denominator and the same 16/16 role
  partition;
- every stage input, stage output, ledger entry, and audit check is addressed;
- the terminal entry is `release-decision` and must agree with the runtime
  state;
- control executions remain held for review and are never promoted by ledger
  construction or recovery routing.

The ledger is evidence of operation closure. It is not a biological result,
clinical decision, treatment recommendation, or claim that a capability is
validated beyond the declared reference-resolution boundary.

## Data model

`FabricOperationLedger` contains the run identity, fixture identity, final
state, conserved counts, and a tuple of `FabricLedgerEntry` values. Each entry
contains:

| Field | Meaning |
| --- | --- |
| `operation_id` | Stable operation identifier derived from stage ordinal and stage ID. |
| `stage_id` | Closed runtime stage name. |
| `ordinal` | One-based execution position. |
| `state` | Observed stage state. |
| `accepted_records` | Count of accepted positive rows carried by the stage. |
| `review_records` | Count of held control rows carried by the stage. |
| `record_count` | Explicit denominator for the stage. |
| `input_address` | Address of the stage input projection. |
| `output_address` | Address of the stage output projection. |
| `content_address` | Address of the ledger entry itself. |

The ledger projection is deliberately counter-oriented. A consumer can
reconcile counts and state transitions without receiving raw record payloads.

## Audit planes

`audit_module_fabric_operation_ledger` evaluates the following invariants:

1. entries exist and include the expected 20-stage runtime surface;
2. ordinals are contiguous and stage IDs are unique;
3. operation IDs and entry addresses are unique and present;
4. stage input and output addresses are present;
5. the record denominator is conserved through every entry;
6. the final entry agrees with the ledger final state;
7. the release decision is retained;
8. optional runtime reconciliation agrees on fixture identity, state, and
   record count;
9. every control execution remains non-accepted.

The audit returns named checks with observed values, required values, detail,
and an address. A mutation of an ordinal, count, stage address, or terminal
state therefore becomes a visible failed check rather than a silently altered
run.

## Recovery routing

`build_module_fabric_recovery_report` converts held control executions into a
review-only queue. Each `FabricRecoveryItem` includes:

- the control record and capability identity;
- the current non-accepted state;
- a bounded action: `review_context_domain_and_source_boundary`;
- required evidence classes: `context_key`, `declared_domain_id`, and
  `public_source_scope`;
- a priority and content address;
- `automatic_promotion=false` as a constructor invariant.

Recovery is a routing mechanism, not an adjudicator. A reviewer may resolve a
control in a later, separately addressed fixture revision. No ledger or
recovery function changes the original execution state.

## Command surface

```text
python -m glio_noncode module-fabric-ledger \
  --output /tmp/module-fabric-ledger.json

python -m glio_noncode module-fabric-ledger-audit \
  --output /tmp/module-fabric-ledger-audit.json

python -m glio_noncode module-fabric-recovery \
  --output /tmp/module-fabric-recovery.json
```

All three commands accept `--input` for a checked-in or locally reviewed
aggregate fixture. The audit command exits nonzero when a blocking invariant
fails. The ledger and recovery outputs are deterministic for the same fixture,
registry, and run identifier.

## Review procedure

An operator should inspect the ledger before reviewing individual controls:

1. confirm the fixture and run identities are the expected addresses;
2. confirm all 20 ordinals are present and contiguous;
3. confirm the denominator is 32 and the role counts are 16 positive / 16
   review;
4. confirm the release decision and final state agree;
5. inspect the recovery queue for held controls;
6. resolve controls only through a new addressed review artifact.

If the ledger audit fails, downstream release use is blocked. The failed check
and its address should be retained with the run packet; the original fixture
must not be rewritten in place.
