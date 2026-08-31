# Recovery execution runtime registry federation

The runtime registry federation is the aggregation boundary above independently verified recovery execution runtime registries. It combines multiple registry receipts into one deterministic, value-free projection while retaining enough source-scoped identity to explain which registry admitted each runtime.

## Contract

Each federation member retains the source registry ID and address, source version and boundary, entry counters, state, acceptance, and its own addressed member record. Flattened runtime entries retain the member ordinal, source registry ID and address, runtime and execution addresses, state, acceptance, and a stable entry address. Admission sorts registries by `(registry_id, registry_address)` and rejects duplicate source identities. Flattened entries are ordered by their admitted member and source runtime order, with duplicate source-scoped runtime identities rejected.

Federation state is explicit: `empty` means no members, `ready` means every member is ready, `mixed` means accepted ready/empty members are present, and `blocked` means at least one member is blocked. Acceptance is true when no member is blocked, so `mixed` is accepted but not ready. Member counts and flattened runtime counts are replayed from the retained projections.

The persisted package contains exactly five canonical UTF-8 JSON files:

- `manifest.json` — federation metadata and links to the member, entry, and summary artifacts;
- `federation.json` — the complete addressed federation projection;
- `members.json` — the source-scoped member collection;
- `entries.json` — flattened runtime-entry provenance; and
- `summary.json` — conserved member, runtime, state, and acceptance counters.

Writes use a temporary sibling directory and atomic replacement. Reload rejects missing or extra members, symlinks, non-regular files, non-canonical JSON, oversized artifacts, stale component addresses, mismatched nested links, and unsupported legacy shapes.

## Assurance and inspection

The independent federation audit recomputes 18 checks for format and boundary, federation/member/runtime addresses, deterministic order, source identity uniqueness, state and count conservation, entry-to-member linkage, summary and manifest linkage, acceptance folding, public-boundary safety, and mapping round trips.

The federation query exposes ten bounded resources: `summary`, `members`, `entries`, `registries`, `runtimes`, `states`, `readiness`, `addresses`, `counts`, and `bounds`. Filters support resource, state, key, text, offset, and limit. The independent query audit recomputes 12 checks for resource order, filter replay, counts, row order and addresses, membership, semantics, federation linkage, public-boundary safety, and mapping round trips.

## Interfaces and real data

The long-form CLI supports federation build, verify, audit, query, query-audit, and all federation/audit/query schema and capability documents. The HTTP API mirrors those operations below the runtime-registry federation route. The downloaded-data demo derives two ready registry members from the supplied ZIP’s archive-recovery execution, persists and reloads the exact five-file federation, and emits JSON/CSV/Markdown assurance and query artifacts without source paths, payload bytes, agent metadata, or language metadata.
