# Recovery Execution Runtime Handoff

The recovery execution runtime is the durable handoff boundary for the
verifiable execution receipts produced by the downloaded-archive recovery
module. It packages one execution projection, its independent execution audit,
its bounded query projection, and the independent query audit into an exact,
reloadable directory. The handoff is useful when a receiver needs to inspect or
verify the recovery result after the original process has ended.

## Package contract

Every persisted runtime contains exactly these seven regular files, in the
canonical order below:

1. `manifest.json` — package identity, version, ordered artifacts, file sizes,
   SHA-256 byte receipts, and artifact addresses.
2. `runtime.json` — the path-free runtime summary, five stage receipts, nested
   execution/audit/query addresses, and acceptance state.
3. `execution.json` — the source execution receipt with planned, progress,
   complete, or blocked state and action outcomes.
4. `execution-audit.json` — the independently recomputed execution audit.
5. `execution-query.json` — the bounded, value-free execution inspection
   projection.
6. `execution-query-audit.json` — the independently recomputed query audit.
7. `summary.json` — the compact handoff summary and public capability facts.

The manifest is generated from the final bytes of the six artifacts. Runtime
addresses are derived from canonical content, not filesystem paths. A writer
builds the complete package in a temporary sibling directory and atomically
renames it into place. Existing destinations require explicit overwrite
permission, and a failed write cannot leave a partially updated destination.

## Stage and state semantics

The runtime exposes five ordered stages: `execution`, `audit`, `query`,
`query-audit`, and `complete`. Each stage records its own address, state, and
acceptance result. A runtime is `ready` only when all nested receipts are
accepted and the complete-stage replay succeeds. Invalid or rejected nested
receipts produce a `blocked` runtime. The state is therefore reproducible from
the persisted files and does not depend on process memory.

Reloading is strict. The loader rejects missing or extra members, directories,
symlinks, non-canonical JSON, mismatched byte sizes, mismatched hashes, stale
manifest addresses, invalid nested links, and runtime summaries that do not
replay to the loaded components. Verification never repairs a package; it
returns a fail-closed validation error so the receiver can retain the original
evidence and decide what to do next.

## Inspection and audit surfaces

The runtime audit independently recomputes 16 conditions covering version and
boundary identity, execution/audit/query linkage, stage count and order,
stage-address conservation, acceptance and state replay, component addresses,
public-boundary constraints, and mapping round trips.

Runtime queries expose seven bounded resources: `summary`, `stages`,
`artifacts`, `components`, `outcomes`, `status`, and `bounds`. Queries support
resource, state, key, text, offset, and limit filters. Returned rows carry stable
row addresses but never expose source paths or payload bytes. The query audit
replays resource ordering, filters, counts, row order and addresses, membership,
resource semantics, runtime linkage, public-boundary rules, and serialization.

JSON, CSV, and Markdown renderings are deterministic. Schemas and capability
documents describe the contracts so a CLI client, HTTP client, or offline
reviewer can discover the same behavior.

## CLI and HTTP API

The CLI uses the recovery execution command prefix with the `-runtime` suffix:

```text
base="downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution"
python -m glio_noncode "${base}-runtime" execution.json --destination runtime --format json
python -m glio_noncode "${base}-runtime-verify" runtime --format json
python -m glio_noncode "${base}-runtime-audit" runtime --format json
python -m glio_noncode "${base}-runtime-query" runtime --resource stages --limit 25 --format json
python -m glio_noncode "${base}-runtime-query-audit" query.json --runtime-input runtime --format json
```

The local HTTP API exposes the same base, `/verify`, `/audit`, `/query`, and
`/query/audit` routes below the downloaded-data recovery execution runtime
prefix. Schema and capability routes are registered in the public-surface
inventory and in CI.

## Downloaded-data demonstration

The product demo runs this boundary against the supplied downloaded ZIP. It
builds the recovery execution from an out-of-order partial receiver, creates a
runtime handoff, persists and reloads the exact package, runs both independent
audits, and emits bounded runtime inspection artifacts. The output contains
only structural counts, decisions, states, addresses, and audit results; it
does not copy source paths, record values, archive payload bytes, agent
metadata, or language metadata into the runtime package.
