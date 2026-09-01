# Exact execution-ledger runtime registry history

The execution-ledger runtime registry history contract records an append-only
sequence of public registry snapshots. Each snapshot retains the registry
identity, addressed content identity, entry counts, readiness state, acceptance
state, transition, and predecessor address. The history is therefore suitable
for offline review without reopening runtime payloads.

## Contract

The history has one stable `history_id` and `registry_id`. Entries are ordered
by ordinal and every entry after the first points to the immediately preceding
registry address. Duplicate registry addresses are rejected. Transition replay
uses five deterministic values:

- `initial` for the first snapshot;
- `improved` when readiness and counts improve;
- `regressed` when the quality rank falls;
- `unchanged` when the public snapshot is identical in quality and counters;
- `changed` for a valid snapshot change that is neither an improvement nor a
  regression.

The latest snapshot supplies the history state and acceptance result. Empty,
ready, and blocked states are preserved. `append_registry` returns a new
history value, leaving the prior value unchanged.

## Exact persistence

`persist_history` writes exactly four canonical files atomically:

```text
manifest.json
history.json
entries.json
summary.json
```

The manifest records byte size and content receipts for the entries and summary
projections. `load_history` rejects missing, extra, symlinked, non-canonical,
tampered, or cross-linked files. The history content address is derived from
the public entries and summary projections, avoiding a circular manifest
dependency.

## Queries and audits

History queries expose `summary`, `snapshots`, `transitions`, `states`,
`readiness`, `addresses`, `bounds`, and `latest` resources. Filters cover
state, transition, key, and text, with deterministic offset/limit pagination.
The independent history audit has 16 replay checks. The independent query
audit has 12 checks covering resource selection, filtering, row addresses,
membership, semantics, linkage, and mapping round trips.

## CLI and HTTP

The exact-prefixed CLI supports construction, verification, audit, query,
query audit, and all contract schemas. A history can be built from persisted
registry directories:

```powershell
python -m glio_noncode <ledger-runtime-registry-history> `
  <registry-empty> --registry-input <registry-current> `
  --history-id downloaded-history --destination history --format summary
python -m glio_noncode <ledger-runtime-registry-history>-audit history
python -m glio_noncode <ledger-runtime-registry-history>-query history `
  --resource transitions --transition regressed --format markdown
```

The local HTTP API mirrors the same base, `/verify`, `/audit`, `/query`,
`/query/audit`, and schema routes under the runtime-registry history path.

## Downloaded-data evidence

The downloaded-data demonstration reads the supplied ZIP, derives execution
receipts, builds an empty baseline and a current registry snapshot, and stores
the resulting history at:

```text
artifacts/exact-execution-ledger-downloaded-data-demo/
  history-diff-archive-transfer-recovery-execution-runtime-registry-history-diff-archive/
    recovery/execution-ledger-runtime-registry-history/
```

It reloads the exact four-file package, writes independent JSON/CSV/Markdown
audit and query projections, and records the transition sequence, state,
acceptance, row totals, and audit results in `summary.json`.
