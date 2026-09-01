# Exact execution ledger

The exact execution ledger is the append-only boundary above the recovery
execution receipt. It retains a bounded, ordered chain of immutable execution
snapshots while keeping the ledger projection independent from the individual
execution, recovery, transfer, and archive contracts.

## Contract

Each entry records:

- ordinal and stable ledger identity;
- execution, recovery, transfer, and archive content addresses;
- planned, in-progress, complete, or blocked state;
- resume, assemble, or block decision and transition;
- applied, pending, and rejected counts;
- received and remaining bytes;
- continuation and assembly safety;
- checkpoint state and ancestry to the preceding entry; and
- four component evidence addresses.

The ledger replays contiguous ordinals, stable component identity, transition
counts, state counts, latest-entry projections, head address, and byte
conservation. Duplicate execution addresses, mixed recovery identities, stale
optimistic head guards, malformed ancestry, and non-canonical projections are
rejected.

An empty ledger is a valid starting point with the fixed head
`exact-history-diff-archive-transfer-recovery-execution-ledger:empty`. Appends
are copy-on-write and accept an optional expected head address, allowing a
caller to detect concurrent writers without mutating the prior value.

## Persistence and inspection

`persist_ledger` writes exactly four canonical files atomically:

1. `manifest.json` — ordered file names and byte receipts;
2. `ledger.json` — the complete addressed ledger projection;
3. `entries.json` — the independently addressed entry projection; and
4. `summary.json` — the bounded summary projection.

`load_ledger` verifies file order, exact bytes, per-file hashes, nested
projections, and all content addresses before returning a typed ledger.

The independent ledger audit exposes 18 replay checks. The bounded query
surface exposes summary, entries, transitions, states, decisions, bytes, and
latest resources, and its independent query audit exposes 12 checks. JSON,
CSV, Markdown, schema, capabilities, CLI, and local HTTP surfaces use the same
typed contract.

## CLI

Build a ledger from ordered execution receipts:

```text
glio-noncode <exact-execution-prefix>-ledger planned.json \
  --execution-input progress.json \
  --execution-input complete.json \
  --destination execution-ledger \
  --format summary
```

Inspect the persisted result:

```text
glio-noncode <exact-execution-prefix>-ledger-verify execution-ledger
glio-noncode <exact-execution-prefix>-ledger-audit execution-ledger
glio-noncode <exact-execution-prefix>-ledger-query execution-ledger --resource transitions
glio-noncode <exact-execution-prefix>-ledger-query-audit query.json --ledger-input execution-ledger
```

The CLI also exposes entry, entries, manifest, summary, ledger, audit, query,
and query-audit schemas and capability documents.

## Downloaded-data evidence

The downloaded-data demo reads the supplied ZIP, derives exact recovery
execution receipts, builds a four-entry planned → in-progress → complete →
blocked ledger, persists and reloads the four-file package, and writes the
independent audit and query projections. The resulting summary reports the
ledger state, transition counts, entry count, query row count, reload address
match, and audit outcomes.
