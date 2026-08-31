# Federation archive-transfer recovery execution runtime registry

This module admits one or more federation archive-transfer recovery execution runtime handoffs into a deterministic, path-free registry. It is the registry boundary after the federation-specific runtime handoff: callers can retain a compact index of ready or blocked runtime receipts without reopening source archives or copying payload data.

## Contract

The registry accepts typed federation-specific `RecoveryExecutionRuntime` values and sorts them by `(runtime_id, runtime_address)`. Duplicate runtime identities are rejected. The registry folds each entry into `empty`, `ready`, or `blocked` state and conserves `entry_count`, `accepted_count`, `ready_count`, and `blocked_count`. An empty registry is structurally valid and remains accepted as an explicit no-members state.

Every persisted registry is exactly four canonical files:

1. `manifest.json` — registry identity, version, boundary, file set, and artifact addresses.
2. `registry.json` — top-level typed registry receipt and nested summary/entries.
3. `entries.json` — ordered runtime admission rows.
4. `summary.json` — compact state and conservation counters.

Writes use an atomic temporary directory and strict replacement policy. Reload verifies the exact member set, canonical JSON bytes, content addresses, manifest linkage, and all derived counters. Non-canonical, tampered, extra-member, and symlinked packages fail closed.

## Assurance and inspection

The independent registry audit emits 16 fixed checks covering version, boundary, address, entry count/order, identity uniqueness, runtime linkage, state/count/acceptance replay, summary/entries/manifest linkage, public-boundary privacy, and mapping round-trip.

The bounded query exposes seven ordered resources: `summary`, `entries`, `runtimes`, `states`, `readiness`, `addresses`, and `bounds`. State, exact-key, case-insensitive text, offset, and limit filters are deterministic. The independent query audit emits 12 checks covering resource order, filter/count replay, row order/address/membership, resource semantics, registry linkage, public boundary, and mapping round-trip.

## CLI and API

The CLI command is the long federation archive-transfer recovery execution runtime registry command ending in `-execution-runtime-registry`. It can build a registry from repeated `--runtime-input` values, persist it with `--destination`, verify and audit a package, query it, and audit a query. Fifteen schema/capability commands cover the registry, audit, query, and query-audit projections.

The local HTTP API mirrors those surfaces below the federation archive-transfer recovery execution runtime path at `/registry`, `/registry/verify`, `/registry/audit`, `/registry/query`, and `/registry/query/audit`, with schema routes for the same projections.

The downloaded-ZIP demo builds the federation-specific runtime from `GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip`, admits it into this registry, persists the exact four-file package, emits JSON review projections, and records content-address evidence in `summary.json` without source paths, source records, payload bytes, or private metadata.
