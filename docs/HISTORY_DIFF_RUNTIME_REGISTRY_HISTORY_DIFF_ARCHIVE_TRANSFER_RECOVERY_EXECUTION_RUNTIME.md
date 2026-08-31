# Exact history-diff archive transfer recovery execution runtime

This boundary is the durable handoff above an exact archive-transfer recovery execution receipt. It packages the execution projection and its independent inspections into one deterministic, path-free runtime value that can be persisted, reloaded, queried, and verified on another machine.

## Composition

The runtime is built from one `ExactHistoryDiffArchiveTransferRecoveryExecution` and automatically derives:

- the 18-check execution audit;
- the bounded seven-resource execution query;
- the 12-check execution query audit; and
- five ordered stages: `execution`, `audit`, `query`, `query-audit`, and `complete`.

The runtime state is `ready` only when the two independent audits pass. Otherwise it is `blocked`. The execution itself may still be `planned`, `in_progress`, `complete`, or `blocked`; the runtime state describes the integrity of the handoff package rather than pretending that a partial transfer is complete.

## Durable package

`persist_runtime` writes exactly seven canonical members atomically:

1. `manifest.json`
2. `runtime.json`
3. `execution.json`
4. `execution-audit.json`
5. `execution-query.json`
6. `execution-query-audit.json`
7. `summary.json`

The manifest records fixed member order, sizes, per-file byte hashes, and the runtime content address. Reloading rejects missing, extra, reordered, non-canonical, tampered, or structurally inconsistent members. The in-memory runtime retains composed typed receipts for persistence, while `to_dict` and all public projections contain only value-free receipt data.

## Review surfaces

The module exposes JSON, CSV, Markdown, schema, and capability projections. The CLI supports build, verify, audit, query, and query-audit commands plus all stage, manifest, runtime, audit, query, and query-audit schemas. The local HTTP API mirrors those operations under the exact recovery execution runtime route. The public inventory registers the complete schema/capability surface and keeps its expected count synchronized.

Queries expose `summary`, `stages`, `artifacts`, `components`, `outcomes`, `status`, and `bounds`, with deterministic filtering, offset, and limit replay. Query assurance checks resource order, filtering, counts, row order, row addresses, membership, semantics, runtime linkage, the public boundary, and mapping round-trip.

## Real downloaded-data evidence

The downloaded-ZIP demo at `examples/downloaded_data_contract_resolution_history_diff_policy_demo.py` builds a five-chunk archive-transfer execution from `C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip`. It persists and reloads in-progress, complete, and blocked execution runtime packages under the generated recovery artifact directory. The in-progress package reports three received chunks, two pending chunks, 2,735 received bytes, 2,048 remaining bytes, five stages, sixteen runtime checks, and twelve query-audit checks; all package reloads and required checks pass.

Focused coverage is provided by `tests/test_exact_history_diff_archive_transfer_recovery_execution_runtime.py`, including persistence, canonical mapping, tamper rejection, CLI, HTTP API, schema, and public inventory checks.
