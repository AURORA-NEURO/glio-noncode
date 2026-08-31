# Downloaded-data federation archive transfer recovery execution

The federation archive transfer recovery execution boundary turns a
path-free recovery plan into a deterministic receipt of which missing-chunk
actions have been applied, remain pending, or were rejected. It carries only
manifest-safe identities, addressed byte ranges, status reasons, conserved
index sets, and byte totals. It never includes local paths, source records,
archive payload bytes, agent metadata, or language metadata.

## Receipt states

A receipt partitions every planned recovery action into exactly one status:

- `pending`: the action still needs a verified chunk;
- `applied`: the action is recorded as satisfied; and
- `rejected`: the action was refused and continuation is blocked.

The derived state is `planned` with no applied actions, `in_progress` with
some applied actions, `complete` when every missing action is applied, and
`blocked` when any action is rejected. The derived decision is `resume`,
`assemble`, or `block`. Base received indexes plus planned indexes cover the
transfer universe. Applied, pending, and rejected indexes partition the plan.
Current received and missing indexes are replayed from those partitions, and
all planned/applied/pending/rejected/current byte totals conserve both the
recovery remainder and the archive size.

`build_execution_from_assembler` verifies the canonical transfer, confirms its
address matches the recovery plan, and derives applied indexes from the actual
receiver state. `build_execution_from_directory` applies the same verification
to a persisted transfer directory. `build_execution` supports value-free
status admission for integrations that already hold independently verified
chunk decisions.

## Independent audit and query

`audit_execution` recomputes 18 fixed checks for recovery and transfer
linkage, plan and current-index conservation, ordered outcomes, status and
byte conservation, state/decision/safety replay, checkpoint/next-index replay,
public-boundary enforcement, mapping round trip, and deterministic outcomes.

`query_execution` exposes seven bounded resources: `summary`, `outcomes`,
`applied`, `pending`, `rejected`, `state`, and `bounds`. It supports resource,
status, index, and text filters, stable pagination, deterministic row
addresses, and JSON/CSV/Markdown projections. `audit_query` independently
replays the filters, counts, row ordering, row membership, resource semantics,
execution linkage, public boundary, and mapping round trip.

## CLI

The full command is:

```text
downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery-execution
```

Examples:

```powershell
$base = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery-execution"

python -m glio_noncode $base recovery.json `
  --applied-index 1 --applied-index 2 --checkpointed `
  --format json --output execution.json
python -m glio_noncode "$base-audit" execution.json --format markdown
python -m glio_noncode "$base-query" execution.json `
  --resource applied --resource pending --format csv
python -m glio_noncode "$base-query-audit" query.json `
  --execution-input execution.json
```

The command family also emits the outcome, receipt, audit, query-row,
query, and query-audit schemas and capability descriptions.

## HTTP API

The base route is:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive/transfer/recovery/execution
```

Use `?input=execution.json&format=json` for a receipt, `/verify` for typed
rehydration, `/audit` for independent checks, `/query` for bounded rows, and
`/query/audit` with separate `input` and `execution_input` documents. Schema
and capability routes are available beneath the execution boundary.

## Downloaded-data demonstration

The real downloaded-ZIP demonstration builds the federation archive transfer,
creates a two-chunk checkpoint with four missing actions, and emits planned,
in-progress, complete, and blocked receipts. It persists canonical JSON, CSV,
Markdown, audit, query, and query-audit artifacts and records the resulting
state, action counts, index partitions, conserved byte totals, next action,
safety decisions, and public addresses in `summary.json`.
