# History-Diff Archive Transfer Recovery Execution Runtime Registry

This boundary admits multiple exact history-diff archive-transfer recovery execution runtime handoffs into one deterministic, public, value-free registry. Each entry preserves the runtime ID, runtime address, execution linkage, readiness state, acceptance, and an independently addressed entry receipt.

## Contract

Entries are sorted by `(runtime_id, runtime_address)`, assigned one-based ordinals, and folded into three states:

- `empty`: no runtime entries; accepted for an intentionally empty registry;
- `ready`: every runtime entry is ready and accepted;
- `blocked`: at least one runtime entry is blocked or not accepted.

Counts, entry order, acceptance, summary linkage, and manifest linkage replay during construction and reload. Public mappings contain no source paths, source records, payload bytes, private metadata, agent metadata, or language metadata.

## Persisted package

`persist_registry` writes exactly four canonical JSON members atomically:

1. `manifest.json` — registry identity, version, boundary, fixed file list, and artifact addresses;
2. `registry.json` — the complete addressed registry contract;
3. `entries.json` — ordered entry projection;
4. `summary.json` — bounded counts and folded state.

Reload requires the exact member set, canonical bytes, valid JSON objects, matching content addresses, and manifest byte hashes. Extra members, missing members, trailing bytes, tampered counts, reordered entries, duplicate identities, or mismatched projections fail closed.

The independent registry audit exposes sixteen checks. The bounded query exposes seven canonical resources: `summary`, `entries`, `runtimes`, `states`, `readiness`, `addresses`, and `bounds`. Its independent query audit exposes twelve checks for version, boundary, resource order, filter/count replay, row order/address/membership, resource semantics, registry linkage, public boundary, and mapping round-trip.

The contract is available through the CLI, local HTTP API, JSON schemas, capability projections, and public-surface inventory. The downloaded-ZIP demonstration builds an in-progress runtime plus a complete runtime from real archive-derived data, persists and reloads the registry, emits JSON/CSV/Markdown review projections, and records registry/query assurance in `summary.json`.

## Review command

```powershell
python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/history-diff-archive-transfer-recovery-execution-runtime-registry-real-downloaded-data-demo
```

The artifact directory contains the exact four-member registry package under `history-diff-archive-transfer-recovery-execution-runtime-registry/` and root convenience projections for the registry, audit, query, and query-audit contracts.
