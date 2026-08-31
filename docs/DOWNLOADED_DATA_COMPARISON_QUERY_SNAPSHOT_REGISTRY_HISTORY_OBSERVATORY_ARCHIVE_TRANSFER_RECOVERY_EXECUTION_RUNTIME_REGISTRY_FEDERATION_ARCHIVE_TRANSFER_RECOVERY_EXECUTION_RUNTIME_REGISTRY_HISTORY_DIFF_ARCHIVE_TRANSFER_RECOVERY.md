# Federation runtime-registry history-diff archive transfer recovery

This boundary turns a persisted or in-memory partial transfer into a compact,
addressed recovery plan. It is the operator-facing continuation of the
history-diff archive transfer contract:

1. The verified history-diff ZIP is represented by a deterministic transfer
   manifest and fixed byte-range chunks.
2. A complete or partial receiver state is folded into a recovery snapshot.
3. Every missing chunk becomes one independently addressed recovery action.
4. The snapshot records whether the receiver must `resume` or may `assemble`.
5. Independent audits and bounded query projections expose the plan without
   exposing source paths, source records, or payload bytes.

## Contract identity

The module is
`history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery.py`.
Its version and boundary are derived from the transfer boundary, so a recovery
snapshot cannot silently refer to an unrelated archive family. Recovery
snapshots and actions are content-addressed from canonical public mappings.

The recovery object contains:

- the recovery and transfer identities;
- the anchored archive address and archive byte count;
- sorted received and missing chunk-index partitions;
- received and remaining byte counts;
- one action for each missing chunk;
- `partial` or `complete` state;
- `resume` or `assemble` decision;
- an explicit `safe_to_resume` flag;
- checkpoint status and the first missing `next_index`;
- a recovery content address.

The action object contains only the missing chunk index, byte offset, byte
size, chunk content address, and action content address. The action is
therefore schedulable by a receiver while remaining value-free at the public
boundary.

## State and decision semantics

The builder accepts either a complete `HistoryDiffArchiveTransfer` or an
assembler-backed receiver. For a complete transfer, all chunk payloads are
already present and the recovery result has:

```text
state=complete
decision=assemble
action_count=0
next_index=-1
```

For an assembler-backed partial receiver, the builder recomputes the sorted
partition from the receiver's receipts. If any chunk is absent, the result
has:

```text
state=partial
decision=resume
safe_to_resume=true
next_index=<first missing chunk index>
```

The builder verifies the transfer manifest before planning. It rejects receipt
indices outside the transfer, preserves the original chunk offsets and sizes,
and ensures that `received_bytes + remaining_bytes == archive_size`.

## Independent recovery audit

`audit_recovery` recomputes the plan from the public recovery snapshot and
emits seventeen addressed checks:

1. version derivation;
2. boundary derivation;
3. recovery-address replay;
4. transfer linkage;
5. archive linkage;
6. received/missing index conservation;
7. byte conservation;
8. one action per missing index;
9. action-address replay;
10. action range containment;
11. state replay;
12. decision replay;
13. next-index replay;
14. checkpoint type;
15. public-boundary enforcement;
16. mapping round-trip;
17. deterministic action-plan replay.

The audit is independent of the builder's private intermediate state. It
reconstructs the expected action addresses from the public action geometry,
then fails closed when any check is not accepted. Each check retains the
recovery address as evidence, and the aggregate audit is itself addressed.

## Query resources

The recovery query exposes seven bounded resources in canonical order:

| Resource | Purpose |
| --- | --- |
| `summary` | one row with recovery, transfer, archive, and progress totals |
| `actions` | missing-chunk actions with offsets, sizes, and addresses |
| `received` | received chunk-index receipts |
| `missing` | missing chunk-index and action geometry |
| `state` | partial/complete state and resume/assemble decision |
| `progress` | received bytes, remaining bytes, and next index |
| `bounds` | maximums and query-contract limits |

Queries support resource selection, chunk-index filtering, state filtering,
receipt filtering, bounded text matching, offset pagination, and a maximum
page size. Query rows are addressed individually and retain the recovery
address, transfer address, archive address, resource, and page ordinal. A
summary row is deliberately distinct from an action or receipt row so a
consumer can distinguish totals from chunk-level operations.

`audit_query` independently recomputes the requested page and emits twelve
checks for version, boundary, resource order, filter replay, count replay,
row order, row addresses, row membership, resource semantics, recovery
linkage, public boundary, and mapping round-trip.

## CLI

The command family uses the long history-diff archive transfer prefix followed
by `-recovery`.

Build a checkpointed plan from a complete or partial transfer directory:

```powershell
python -m glio_noncode <history-diff-archive-transfer-prefix>-recovery `
  C:\data\history-diff-archive-transfer-partial `
  --recovery-id downloaded-history-diff-recovery `
  --format json `
  --output C:\data\history-diff-recovery.json
```

Verify or audit a recovery JSON document:

```powershell
python -m glio_noncode <history-diff-archive-transfer-prefix>-recovery-verify `
  C:\data\history-diff-recovery.json --format summary
python -m glio_noncode <history-diff-archive-transfer-prefix>-recovery-audit `
  C:\data\history-diff-recovery.json --format markdown
```

Inspect missing actions and progress:

```powershell
python -m glio_noncode <history-diff-archive-transfer-prefix>-recovery-query `
  C:\data\history-diff-recovery.json --resource missing --resource progress `
  --limit 32 --format json
```

Audit a previously emitted query page:

```powershell
python -m glio_noncode <history-diff-archive-transfer-prefix>-recovery-query-audit `
  C:\data\history-diff-recovery-query.json `
  --recovery-input C:\data\history-diff-recovery.json --format summary
```

The CLI also exposes action, recovery, audit, query-row, query, query-audit,
and capability schemas. JSON, CSV, Markdown, and summary projections use the
same typed validation path.

## HTTP API

The local API mirrors the CLI below the history-diff archive transfer route:

```text
.../history-diff-archive/transfer/recovery
.../history-diff-archive/transfer/recovery/verify
.../history-diff-archive/transfer/recovery/audit
.../history-diff-archive/transfer/recovery/query
.../history-diff-archive/transfer/recovery/query/audit
```

The base route accepts a transfer directory through `input` or `transfer` and
returns the recovery projection. Verification, audit, query, and query-audit
routes accept JSON document paths through `input`/`recovery` and
`recovery_input` where two documents are required. Schema routes are available
for the action, recovery, audit, query, and query-audit contracts.

## Downloaded-data demonstration

`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`
loads the supplied downloaded ZIP, builds the exact history-diff archive,
transfers it in fixed chunks, receives the first and last chunks out of order,
and derives the recovery plan. It persists the plan, audit, query, and
query-audit artifacts beside the transfer directory, reloads the partial
directory, and checks that all public addresses and audit results replay.

The demonstration also builds a complete recovery snapshot from the fully
received transfer. This proves both decision branches against the same
downloaded archive: the partial receiver reports `resume` with missing
actions, while the complete receiver reports `assemble` with no actions.

## Failure behavior

The boundary fails closed for unknown fields, malformed addresses, duplicate
or unordered action records, inconsistent counts, overlapping index
partitions, invalid archive ranges, non-boolean checkpoint flags, failed
content-address replay, and query pages that do not reproduce independently.
No recovery operation mutates the source transfer directory; persistence of
recovery projections is an explicit caller action.
