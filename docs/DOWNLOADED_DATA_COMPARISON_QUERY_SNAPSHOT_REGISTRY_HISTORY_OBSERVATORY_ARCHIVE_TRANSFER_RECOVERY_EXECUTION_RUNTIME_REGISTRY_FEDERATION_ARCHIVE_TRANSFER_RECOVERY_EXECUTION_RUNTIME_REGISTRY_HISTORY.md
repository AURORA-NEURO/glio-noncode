# Federation runtime-registry history

The federation-specific recovery execution runtime registry history boundary is an append-only, path-free ledger of registry snapshots. It preserves the registry identity, addressed snapshot ancestry, acceptance/readiness counts, and a deterministic transition classification for every accepted snapshot in submission order.

## Contract

The history admits zero or more typed federation-specific runtime registries with one stable `registry_id`. Duplicate registry content addresses are rejected. Each entry records:

- the ordinal and registry content address;
- entry, accepted, ready, and blocked counts;
- the folded state and acceptance result;
- `initial`, `improved`, `regressed`, `unchanged`, or `changed` transition classification; and
- the previous registry address when ancestry exists.

An empty history is explicit and has `state=empty` and `accepted=false`. A non-empty history inherits the latest registry state and acceptance. Quality ordering is deterministic: ready is better than empty, and empty is better than blocked; equal quality with changed counts is classified as `changed`.

## Persistence and assurance

`persist_history` atomically writes exactly four canonical JSON members:

1. `manifest.json` — version, boundary, exact file set, and component addresses;
2. `history.json` — the complete replayable history;
3. `entries.json` — the ordered snapshot projection; and
4. `summary.json` — latest metrics and transition counters.

Reload checks the exact member set, regular-file requirement, canonical bytes, size bounds, nested addresses, component equality, and manifest linkage. The independent history audit has 16 fixed checks covering identity, ancestry, transition replay, counts, component linkage, the public boundary, and mapping round trips.

## Query surfaces

The bounded query surface exposes `summary`, `snapshots`, `transitions`, `states`, `readiness`, `addresses`, and `bounds`. Queries support resource selection, state/key/transition/text filters, stable pagination, row addresses, and deterministic JSON, CSV, Markdown, or summary projections. The independent query audit has 12 checks for resource order, filter and count replay, row membership, semantics, linkage, and round trips.

The CLI command is the federation runtime-registry command with `-history` appended. It supports repeated `--registry-input` values for building a history, verification, audit, query, query audit, and 15 schema/capability commands. The local HTTP API appends `/history`, `/verify`, `/audit`, `/query`, `/query/audit`, and the matching schema/capability routes.

The downloaded-data demo builds a two-snapshot history from the real ZIP workflow: an explicit empty baseline followed by a ready registry. It persists and reloads the four-file history, records an `initial` plus `improved` transition, runs all 16 history checks, emits all query resources, and runs all 12 query-assurance checks.
