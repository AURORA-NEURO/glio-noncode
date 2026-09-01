# Exact execution-ledger runtime registry

The exact execution-ledger runtime registry is the deterministic admission
boundary above individual ledger-runtime handoffs. It keeps multiple runtime
receipts in one addressed, bounded registry so a transfer or release surface
can evaluate a set of handoffs without changing any admitted runtime.

## Contract

Each admitted entry records the runtime identity, runtime and ledger addresses,
the nested audit/query addresses, the five-stage count, folded state, and
acceptance. Entries are sorted by `(runtime_id, runtime_address)` and assigned
one-based ordinals. A duplicate identity is rejected, and `admit_runtime` is
copy-on-write: an existing registry is never mutated.

The registry folds entries into three states:

1. `empty` — no runtimes have been admitted and the registry is accepted;
2. `ready` — every admitted runtime is ready and accepted; or
3. `blocked` — at least one admitted runtime is blocked or unaccepted.

The registry never upgrades a blocked runtime. Its acceptance is true only for
an empty registry or when every admitted runtime is accepted.

## Persistence and tamper controls

`persist_registry` writes exactly four canonical files atomically:

1. `manifest.json` — ordered file names, artifact names, sizes, and hashes;
2. `registry.json` — the complete nested registry projection;
3. `entries.json` — the ordered entry projection; and
4. `summary.json` — conserved counts, folded state, and acceptance.

`load_registry` rejects symlinks, missing or extra files, non-canonical JSON,
changed bytes, receipt mismatches, altered nested addresses, and non-replayed
counts or state. The registry audit independently recomputes 16 checks. The
registry query exposes eight bounded resources—summary, entries, states,
acceptance, runtimes, addresses, bounds, and latest—with state/key/text filters
and deterministic pagination. Its query audit independently recomputes 12
checks.

## CLI and HTTP

Build a registry from one or more exact runtime packages or runtime JSON
documents:

```text
glio-noncode <exact-ledger-runtime-prefix>-registry runtime-a.json \
  --runtime-input runtime-b.json \
  --registry-id downloaded-runtime-registry \
  --destination execution-ledger-runtime-registry \
  --format summary
```

Inspect it with the matching `-verify`, `-audit`, `-query`, and `-query-audit`
commands. The CLI also exposes entry, entries, artifact, manifest, summary,
registry, audit, query, and query-audit schemas and capability documents. The
local HTTP surface is below the exact ledger runtime route at `/registry`,
including `/registry/verify`, `/registry/audit`, `/registry/query`, and
`/registry/query/audit`.

## Downloaded-data evidence

The downloaded-data demo admits two runtime handoffs derived from the attached
ZIP’s real archive-derived execution receipts. It persists and reloads the
exact four-file registry package, writes separate audit/query inspection
projections, and reports the registry entry count, folded state, acceptance,
16/16 registry-audit checks, deterministic query counts, and 12/12 query-audit
checks.
