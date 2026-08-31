# Federation runtime-registry history-diff archive transfer recovery execution

This boundary records the public execution receipt for a recovery plan over a
federation runtime-registry history-diff archive transfer. It is deliberately
separate from recovery planning: planning describes what is missing, while an
execution receipt records which planned chunk actions were applied, which are
still pending, and which were rejected.

## Contract identity

The module is
`history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution.py`.
Its version, boundary, transfer address, archive address, and recovery address
are replayable from public mappings. The receipt never includes source paths,
source records, archive payload bytes, or private runtime metadata.

Each outcome contains a planned chunk index, action address, chunk address,
offset, size, status, reason, and outcome address. The enclosing execution
contains the conserved base/current index partitions and byte totals, the
checkpoint and next-index projections, and a content address over the complete
canonical mapping.

## State machine

The builder supports four deterministic states:

| State | Meaning | Decision |
| --- | --- | --- |
| `planned` | no planned action has been applied or rejected | `resume` |
| `in_progress` | at least one action is applied and work remains | `resume` |
| `complete` | every planned action is applied | `assemble` |
| `blocked` | at least one planned action is rejected | `block` |

`build_execution_from_assembler` derives applied indices from an independently
verified transfer assembler. Direct construction accepts explicit applied and
rejected index partitions for persisted replay, while rejecting out-of-plan,
overlapping, duplicate, and byte-inconsistent outcomes. `safe_to_continue`
is false only for a blocked receipt; `safe_to_assemble` is true only when no
pending or rejected outcomes remain.

## Independent audit

`audit_execution` reconstructs the receipt from its public geometry and emits
eighteen checks covering:

1. version and boundary derivation;
2. execution address replay;
3. recovery, transfer, and archive linkage;
4. base, planned, applied, pending, rejected, and current index conservation;
5. planned, applied, pending, rejected, and current byte conservation;
6. one outcome per planned action;
7. outcome-address replay;
8. status, state, decision, safety, checkpoint, and next-index replay;
9. outcome geometry and public-boundary enforcement; and
10. canonical mapping replay.

The audit has its own addressed mapping and JSON, CSV, and Markdown exports.
Tampering with a receipt or audit fails closed during mapping reconstruction.

## Bounded query plane

`query_execution` exposes seven resources: `summary`, `outcomes`, `applied`,
`pending`, `rejected`, `state`, and `bounds`. Queries support status, index,
text, offset, and limit filters while preserving canonical row order and
bounded output. Query audits independently verify resource selection, filters,
ordinals, counts, truncation, row addresses, and mapping replay with twelve
checks.

The CLI prefix is the long public command ending in
`history-diff-archive-transfer-recovery-execution`. It provides verify, audit,
query, query-audit, twelve schema/capability endpoints, assembler input, and
applied/rejected index controls. The HTTP API mirrors these routes under
`/downloaded-data/.../history-diff-archive-transfer-recovery/execution`.

## Real downloaded-data demonstration

Run the existing demo with the attached ZIP:

```text
python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py \
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
  artifacts/history-diff-archive-transfer-recovery-real-downloaded-data-demo-2026-08-31
```

The demo builds a valid history-diff archive from the downloaded structural
data, transfers it in fixed chunks, records a partial receiver, emits planned,
in-progress, complete, and blocked receipts, reloads the in-progress receipt
from canonical JSON, and persists the receipt, audit, query, query audit, and
negative-control JSON/CSV/Markdown artifacts. The final summary reports the
archive size, chunk partitions, receipt state, safety decisions, addresses,
audit counts, and exact reassembly status.

No external repository or prior codebase is required to exercise this
boundary. The public contract remains useful with only the downloaded ZIP and
the repository’s deterministic structural fixtures.
