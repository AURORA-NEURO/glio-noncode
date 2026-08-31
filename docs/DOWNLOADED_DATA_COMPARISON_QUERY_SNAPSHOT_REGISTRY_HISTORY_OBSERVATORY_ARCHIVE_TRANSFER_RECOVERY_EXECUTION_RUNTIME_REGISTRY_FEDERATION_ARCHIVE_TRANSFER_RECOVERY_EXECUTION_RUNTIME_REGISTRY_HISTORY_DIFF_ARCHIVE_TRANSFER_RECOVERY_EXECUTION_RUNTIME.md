# Federation runtime-registry history-diff archive transfer recovery execution runtime

This boundary is the durable runtime handoff above the history-diff archive
transfer recovery execution receipt. It packages the execution decision and
its independent evidence into one reloadable, value-free runtime state.

## Contract identity

The module is
`history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime.py`.
Its public mapping contains the runtime identity, execution linkage, five
ordered stages, ready/blocked state, acceptance, and a content address. It
does not contain source paths, source records, archive payload bytes, agent
metadata, or language metadata.

## Runtime stages and persistence

The handoff stages are `execution`, `audit`, `query`, `query-audit`, and
`complete`. A ready runtime requires the execution audit and query audit to
pass; a blocked runtime preserves the same linkage while exposing the failed
acceptance state. The exact seven-file package is:

```text
manifest.json
runtime.json
execution.json
execution-audit.json
execution-query.json
execution-query-audit.json
summary.json
```

`persist_runtime` writes the package atomically. `load_runtime` requires the
exact file set, canonical JSON, replayable addresses, manifest byte receipts,
and matching composed component projections. Any changed member, manifest,
address, stage, or audit linkage fails closed.

## Independent inspection

`audit_runtime` emits sixteen checks covering version and boundary derivation,
execution and component address linkage, stage ordering, state and acceptance
replay, manifest geometry, public-boundary enforcement, and canonical mapping
replay. `query_runtime` exposes seven bounded resources: `summary`, `stages`,
`artifacts`, `components`, `outcomes`, `status`, and `bounds`. Its independent
query audit emits twelve checks for resource order, filters, pagination,
counts, row addresses, runtime linkage, and canonical replay.

## CLI and HTTP surfaces

The CLI prefix is the long public command ending in
`history-diff-archive-transfer-recovery-execution-runtime`. It supports
runtime construction from an execution receipt, exact-directory verification,
independent audit, bounded query, query audit, and stage, manifest, runtime,
audit, query, and query-audit schema/capability projections. The local HTTP
API mirrors those operations under
`/downloaded-data/.../history-diff-archive-transfer-recovery/execution/runtime`.

## Real downloaded-data demonstration

Run the demo with the attached ZIP:

```text
python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py \
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
  artifacts/history-diff-archive-transfer-recovery-real-downloaded-data-demo-2026-08-31
```

The demo builds the execution runtime from a partially received transfer,
audits every composed projection, persists and reloads the exact package,
emits JSON/CSV/Markdown review projections, and records runtime state, stage
count, content-address replay, audit counts, query counts, and query-audit
acceptance in `summary.json`.
