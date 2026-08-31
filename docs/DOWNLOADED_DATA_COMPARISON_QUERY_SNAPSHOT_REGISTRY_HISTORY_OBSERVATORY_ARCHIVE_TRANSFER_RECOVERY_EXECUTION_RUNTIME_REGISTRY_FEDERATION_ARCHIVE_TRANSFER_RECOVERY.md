# Federation archive transfer recovery

The federation archive transfer recovery boundary turns a persisted complete or
partial transfer directory into a path-free continuation plan. It is designed
for the exact transfer produced by
`history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer`.

## Contract

`build_recovery` accepts a verified `ArchiveTransfer` or `TransferAssembler`.
`build_recovery_from_directory` loads the canonical transfer manifest and any
received chunks, then marks the resulting plan as checkpointed. The public
contract contains:

- received and missing chunk indexes, in sorted conserved sets;
- received and remaining byte counts, conserved against the archive size;
- one addressed action for every missing chunk, including its offset, size,
  chunk receipt, and action address;
- `partial`/`resume` or `complete`/`assemble` state and decision projections;
- `safe_to_resume`, checkpoint state, and the next missing index; and
- a deterministic recovery content address.

No source paths, source records, chunk payload bytes, agent metadata, or
language metadata cross this boundary. A complete transfer with all payloads
available produces an `assemble` plan with no actions. A partial transfer
produces a `resume` plan whose actions are sufficient to request every missing
range without relying on local path state.

## Independent audits

`audit_recovery` rematerializes the recovery mapping before checking 15
invariants: version, boundary, address replay, index conservation, byte
conservation, action coverage, action-address replay, archive-range bounds,
state replay, decision replay, next-index replay, checkpoint replay, public
boundary, mapping round-trip, and deterministic action-plan replay. The audit
has canonical JSON, CSV, and Markdown projections and a content address that
changes if any observed or expected evidence changes.

## Bounded queries

`query_recovery` exposes six bounded resources: `summary`, `actions`,
`received`, `missing`, `state`, and `bounds`. Queries support resource order,
chunk-index, state, received-state, text, offset, and limit filters. Each row
has a deterministic address and carries recovery linkage, state/decision
semantics, byte bounds, and the public chunk/action addresses needed for
offline review. `audit_query` independently replays the query shape, row
ordering, row addresses, resource semantics, recovery linkage, and mapping
round-trip through 12 checks.

## CLI and HTTP API

The long-form CLI prefix is the federation archive transfer command with
`-recovery` appended. The base command accepts a complete or partial transfer
directory and emits summary, JSON, CSV, or Markdown. `-verify`, `-audit`,
`-query`, and `-query-audit` cover verification and inspection. Twelve schema
and capability commands publish the action, recovery, audit, query, and
query-audit contracts.

The local HTTP API mirrors the same boundary at `/recovery`, `/recovery/verify`,
`/recovery/audit`, `/recovery/query`, and `/recovery/query/audit` beneath the
federation archive transfer route, with matching schema endpoints. All inputs
are reloaded through the strict transfer/recovery validators.

## Downloaded-data demonstration

The real downloaded ZIP demo creates a 5,709-byte federation archive, splits it
into six 1,024-byte chunks, checkpoints chunks `0` and `5`, and derives a
partial recovery plan with missing chunks `1`, `2`, `3`, and `4`. It reports
1,613 received bytes, 4,096 remaining bytes, next index `1`, four addressed
resume actions, a passing 15-check recovery audit, and a passing 12-check
query audit. It also materializes a full-transfer `assemble` plan and persists
JSON, CSV, and Markdown recovery/query/audit artifacts beside the transfer
directories.
