# Execution-ledger runtime registry history diff

This boundary compares two persisted execution-ledger runtime registry histories. The baseline and candidate must carry the same registry identity; history identifiers and content addresses may differ. Each ordinal is matched deterministically, so the result explains exactly what was retained, introduced, removed, or changed between the two histories.

## Comparison contract

The diff emits one addressed item for every ordinal in the larger history:

- `unchanged`: both histories contain equal public entry snapshots;
- `changed`: both histories contain snapshots, with ordered field-level deltas;
- `added`: only the candidate contains the ordinal;
- `removed`: only the baseline contains the ordinal.

Changed items retain both entry addresses and both public snapshots. The comparison also records the baseline and candidate history addresses, history identifiers, item counts, each change count, and the final direction. Direction is derived from the latest available registry quality: `improved`, `regressed`, `changed`, or `unchanged`. Acceptance is conservative and requires both input histories to be accepted.

## Exact persistence

`persist_diff` writes an atomic four-file package:

1. `manifest.json` — version, boundary, identity linkage, exact member order, and artifact receipts;
2. `diff.json` — the complete top-level comparison contract;
3. `items.json` — ordered comparison items and their item projection address;
4. `summary.json` — counts, direction, acceptance, and history linkage.

The items and summary artifacts carry canonical byte sizes and hashes in the manifest. Reloading requires the exact regular-file set, canonical JSON, replayed content addresses, matching artifact receipts, and nested projection equality. Extra members, modified summaries, non-canonical bytes, and mismatched addresses fail closed.

## Review and query surfaces

The independent diff audit replays sixteen checks covering version, boundary, identity, history linkage, ordinal order, change classification, field deltas, counts, direction, acceptance, item and projection addresses, manifest receipts, public shape, and mapping round-trip.

The bounded query surface exposes nine ordered resources: `summary`, `items`, each change class (`added`, `removed`, `changed`, `unchanged`), `addresses`, `bounds`, and `latest`. Queries support resource selection, change filtering, key filtering, text filtering, deterministic offsets, and bounded limits. Every row has an address and preserves the relevant baseline and candidate entry addresses. The independent query audit replays thirteen checks, including filter and pagination replay, row membership, row semantics, address replay, diff linkage, public shape, and JSON round-trip.

The boundary is available through the exact-prefixed CLI commands, the local HTTP API, JSON schemas, capability documents, and the repository public-surface audit. Its focused regression suite covers same-identity validation, every change class, persistence, tamper rejection, HTTP behavior, CLI behavior, pagination, and schema projections.

## Downloaded-data demonstration

The downloaded-data demo builds the candidate history from the real ZIP-derived execution-ledger runtime registry. It compares that history with a real empty-registry baseline, persists and reloads the four-file diff package, and writes JSON, CSV, and Markdown audit/query evidence under:

`artifacts/exact-execution-ledger-downloaded-data-demo/execution-ledger-runtime-registry-history-diff`

For a blocked candidate, the comparison intentionally reports a `regressed` direction and `accepted: false` while its structural diff audit and query audit remain accepted. This keeps data quality state separate from contract integrity: the package can be inspected and replayed even when the candidate is not release-ready.
