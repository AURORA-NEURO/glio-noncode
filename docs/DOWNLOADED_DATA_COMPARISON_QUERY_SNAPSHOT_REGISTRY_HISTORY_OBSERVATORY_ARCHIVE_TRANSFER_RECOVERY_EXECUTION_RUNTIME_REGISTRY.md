# Recovery execution runtime registry

The recovery execution runtime registry is the next durable boundary above an independently verified runtime handoff. It admits multiple runtime receipts into one deterministic, value-free registry so a downloaded-data workflow can compare and review several execution attempts without reopening source payloads.

## Contract

Each entry retains only the runtime identity, runtime/execution/audit/query addresses, state, and acceptance bit. Admission sorts entries by `(runtime_id, runtime_address)` and rejects duplicate identity pairs. The registry folds entries into `empty`, `ready`, or `blocked`: an empty registry is accepted, a non-empty registry is ready only when every entry is accepted, and any blocked entry blocks the registry. `entry_count`, `accepted_count`, `ready_count`, and `blocked_count` are replayed from the entries.

The persisted package contains exactly four canonical UTF-8 JSON files:

- `manifest.json` — registry metadata and links to the entry and summary artifacts;
- `registry.json` — the complete addressed registry projection;
- `entries.json` — the independently addressed entry collection; and
- `summary.json` — the conserved state and count projection.

Writes use a temporary sibling directory and an atomic replace. Reload rejects missing or extra members, symlinks, non-regular files, non-canonical JSON, oversized artifacts, mismatched component addresses, and stale nested links.

## Assurance and inspection

The independent registry audit recomputes 16 checks covering version and boundary, address and order replay, identity uniqueness, runtime linkage, state and count conservation, acceptance, summary/entry/manifest links, public-boundary safety, and mapping round trips. The registry query exposes seven bounded resources: `summary`, `entries`, `runtimes`, `states`, `readiness`, `addresses`, and `bounds`. Its independent query audit recomputes 12 checks for resource order, filter replay, counts, row order and addresses, membership, semantics, registry linkage, public-boundary safety, and mapping round trips.

## Interfaces and real data

The long-form CLI exposes registry build, verify, audit, query, query-audit, and all registry/audit/query schemas and capability documents. The HTTP API mirrors those operations below the recovery execution runtime route. The downloaded-data demo reads the supplied ZIP, builds two independently addressed runtime entries from the real archive-derived execution, persists the exact registry, and emits registry assurance and query artifacts. Public outputs intentionally exclude source paths, payload bytes, agent metadata, and language metadata.
