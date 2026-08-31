# Exact history-diff archive transfer recovery execution

This boundary turns an addressed recovery plan into a deterministic execution receipt. It is intentionally small and composable: the recovery plan remains the source of missing-chunk actions, while the execution receipt records what was applied, what is still pending, and what was rejected.

## Contract

Each receipt is linked to one exact recovery plan, transfer, and archive address. For every planned chunk it records a public action address, byte offset, byte size, status, reason, and outcome address. Statuses are `pending`, `applied`, and `rejected`.

The receipt derives four state classes:

| State | Meaning | Decision |
| --- | --- | --- |
| `planned` | no recovery action has been applied | `resume` |
| `in_progress` | at least one action is applied and work remains | `resume` |
| `complete` | every planned action is applied | `assemble` |
| `blocked` | at least one action is rejected | `block` |

The contract conserves the recovery plan and current receiver state. Planned, applied, pending, and rejected indexes are disjoint partitions; their byte totals equal the planned byte total; and current received plus current remaining bytes equal the archive size. `next_index`, `checkpointed`, `safe_to_continue`, and `safe_to_assemble` are derived projections rather than caller-supplied hints.

## Verified real-data flow

The downloaded-ZIP demo reads the supplied archive, builds the exact five-chunk transfer, persists a partial receiver, and rebuilds the recovery plan from that receiver directory. It then applies the first missing chunk through a separate assembler and emits three receipts:

- disk-reconstructed `planned`: the persisted checkpoint is still untouched;
- `in_progress`: chunk `1` is applied while chunks `2` and `3` remain pending;
- `blocked`: chunk `1` is explicitly rejected and the decision is fail-closed `block`;
- `complete`: the full receiver assembles and the decision becomes `assemble`.

The attached ZIP run reports a 4,783-byte archive, current received indexes `0,1,4`, 2,735 current received bytes, and 2,048 current remaining bytes. The execution audit passes 18 checks; the seven-resource query returns nine rows and its independent query audit passes 12 checks. JSON, CSV, and Markdown receipts are persisted and reloaded through typed mappings.

## Interfaces

The four Windows-safe modules are:

- `exact_history_diff_archive_transfer_recovery_execution.py` — receipt construction, verification, and projections;
- `exact_history_diff_archive_transfer_recovery_execution_audit.py` — independent invariant replay;
- `exact_history_diff_archive_transfer_recovery_execution_query.py` — bounded summary, outcome, status, and bounds resources;
- `exact_history_diff_archive_transfer_recovery_execution_query_audit.py` — independent query replay.

The CLI exposes the base, `verify`, `audit`, `query`, and `query/audit` commands plus outcome, receipt, audit, query, and query-audit schemas, capabilities, and public projections. The local HTTP API exposes the same contract beneath the exact recovery execution route. The public inventory and Actions workflow exercise all twelve schema/capability projections and the focused regression suite.

All public projections are value-free and preserve only addressed contract data; the source archive and chunk payloads remain outside the receipt surface.
