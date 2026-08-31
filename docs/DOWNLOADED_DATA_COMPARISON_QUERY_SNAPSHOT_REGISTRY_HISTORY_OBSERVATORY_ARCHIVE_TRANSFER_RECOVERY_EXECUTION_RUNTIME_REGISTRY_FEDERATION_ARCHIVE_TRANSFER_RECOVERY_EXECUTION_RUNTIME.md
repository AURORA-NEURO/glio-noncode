# Downloaded-data federation archive recovery execution runtime

The federation archive recovery execution runtime is the durable handoff
around one verified recovery execution receipt. It binds the execution,
its independent audit, a bounded execution query, and the independent query
audit into one path-free runtime identity. The runtime carries identities,
addresses, state, acceptance, stage receipts, and byte-safe artifact metadata;
it does not carry source paths, source records, archive payload bytes, agent
metadata, or language metadata.

## Five-stage handoff

The runtime has a fixed, replayable stage sequence:

1. `execution` confirms that the federation-specific execution receipt is
   structurally valid;
2. `audit` records the 18-check execution audit address and acceptance;
3. `query` records the bounded seven-resource execution query address;
4. `query-audit` records the 12-check query-audit address and acceptance; and
5. `complete` folds the component results into `ready` or `blocked`.

The runtime is `ready` only when both independent audits pass. Every stage
has a deterministic address, state, acceptance flag, detail, and content
address. `verify_runtime` replays the state, stage order, component linkage,
and runtime content address before any projection or persistence.

## Exact persistence contract

`persist_runtime` writes an atomic directory containing exactly these seven
canonical members:

```text
manifest.json
runtime.json
execution.json
execution-audit.json
execution-query.json
execution-query-audit.json
summary.json
```

The manifest records the ordered file set, byte sizes, per-file hashes, file
content addresses, and the runtime address. `load_runtime` rejects symlinks,
unexpected members, non-canonical JSON, changed bytes, mismatched manifests,
broken nested receipts, and any cross-link or address that does not replay.

## Audit and query

`audit_runtime` independently checks the version and boundary, runtime and
component linkage, canonical five-stage order, stage addresses, acceptance
folding, state replay, public-boundary behavior, and mapping round trips in
16 fixed checks.

`query_runtime` exposes seven value-free resources: `summary`, `stages`,
`artifacts`, `components`, `outcomes`, `status`, and `bounds`. It supports
resource, state, key, and text filters with deterministic pagination and
stable row addresses. `audit_query` replays the selected resources, filters,
counts, row order, membership, semantics, runtime linkage, public boundary,
and mapping round trip in 12 fixed checks.

## CLI

The full runtime command is:

```text
downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery-execution-runtime
```

Examples:

```powershell
$base = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-transfer-recovery-execution-runtime"

python -m glio_noncode $base execution.json `
  --destination execution-runtime --overwrite --format json `
  --output runtime.json
python -m glio_noncode "$base-audit" execution-runtime --format markdown
python -m glio_noncode "$base-query" execution-runtime `
  --resource stages --resource components --format csv
python -m glio_noncode "$base-query-audit" query.json `
  --runtime-input execution-runtime --format summary
```

The family also provides stage, manifest, runtime, audit, query-row,
query, and query-audit schemas plus capability descriptions.

## HTTP API

The base route is:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive/transfer/recovery/execution/runtime
```

Use `?input=execution.json&format=json` to build a runtime, or point `input`
at the persisted runtime directory to reload it. `/verify`, `/audit`, and
`/query` provide the corresponding projections. `/query/audit` accepts a
query JSON document plus a separate `runtime_input`. Schema and capability
routes are available below the runtime boundary.

## Real downloaded-ZIP demonstration

The downloaded-data demo reads the attached ZIP, builds the federation
archive and 1,024-byte transfer, creates an out-of-order checkpoint, executes
the two applied chunks while leaving the remaining actions pending, and then
builds this runtime handoff. Its `summary.json` reports the runtime state,
five-stage acceptance, 16-check runtime audit, seven-resource query totals,
12-check query audit, content addresses, exact persisted files, and the
runtime directory for inspection.
