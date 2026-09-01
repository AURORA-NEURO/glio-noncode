# Exact execution-ledger runtime

The exact execution-ledger runtime is the durable handoff above the append-only
execution ledger. It composes the ledger with its independent audit, bounded
query, and query-audit receipts, then replays the result as a five-stage
ready/blocked state machine.

## Contract

The stages are fixed and ordered:

1. `ledger` — the latest ledger projection is accepted or blocked;
2. `audit` — the independent 18-check ledger audit is accepted;
3. `query` — the bounded ledger query is materialized;
4. `query-audit` — the independent 12-check query audit is accepted; and
5. `complete` — the handoff is ready only when the ledger and both audits are
   accepted.

The runtime never upgrades a blocked ledger. A blocked latest execution remains
visible in the first and final stages, while audit and query stages can still
prove structural integrity. Every stage, component, and runtime projection has
an independently replayable content address.

## Persistence and tamper controls

`persist_runtime` writes exactly seven canonical files atomically:

1. `manifest.json` — ordered member names and byte receipts;
2. `runtime.json` — the five-stage handoff projection;
3. `ledger.json` — the complete nested ledger;
4. `ledger-audit.json` — the nested independent ledger audit;
5. `ledger-query.json` — the nested bounded ledger query;
6. `ledger-query-audit.json` — the nested independent query audit; and
7. `summary.json` — the bounded runtime summary.

`load_runtime` rejects symlinks, missing or extra files, non-canonical JSON,
changed member bytes, mismatched manifest receipts, altered nested addresses,
and stage/component mismatches. The runtime audit exposes 16 independent
checks. The runtime query exposes nine path-free resources with state, key, and
text filters plus deterministic pagination. Its query audit exposes 12
independent checks.

## CLI and HTTP

Build a runtime from an exact ledger package or ledger JSON:

```text
glio-noncode <exact-ledger-prefix>-runtime execution-ledger.json \
  --runtime-id downloaded-ledger-runtime \
  --destination execution-ledger-runtime \
  --format summary
```

Inspect it with the matching `-verify`, `-audit`, `-query`, and `-query-audit`
commands. The CLI also exposes stage, artifact, manifest, summary, runtime,
audit, query, and query-audit schemas and capability documents. The local HTTP
surface is available below the exact ledger route at `/runtime`, including
`/runtime/verify`, `/runtime/audit`, `/runtime/query`, and
`/runtime/query/audit`.

## Downloaded-data evidence

The downloaded-data demo builds the runtime from the attached ZIP’s real
archive-derived execution receipts. It persists and reloads the exact
seven-file runtime package, writes separate human-readable audit/query
inspection projections, and reports five stages, the blocked terminal state,
16/16 runtime-audit checks, 12/12 query-audit checks, 30 query rows, and the
reload address match.
