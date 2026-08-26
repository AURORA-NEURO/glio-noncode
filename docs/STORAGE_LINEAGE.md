# Storage lineage

Storage lineage is the read-only provenance view over the local content-addressed
store. It turns the store audit into an inspectable graph of persisted roots,
object addresses, unresolved addresses, and orphan objects. The graph is an
address-only projection: object bytes and scientific payloads remain behind the
store boundary.

## What the graph represents

Every persisted run and batch index becomes a root node. Every valid object
file becomes an `object` node. An object that is valid but not reachable from
any run or batch root becomes an `orphan` node. An address named by a pointer or
object reference but not present in the store becomes a `missing` node. The
graph therefore preserves both trusted structure and the gaps that prevent a
consumer from claiming complete provenance.

Nodes contain only:

- a stable node identifier and typed node kind;
- the content address when the node represents an object address;
- a relative persisted path when one exists;
- acceptance, root, and reference state;
- breadth-first depth from a persisted root and in/out degree counts;
- a content address for the node record.

Edges contain only a stable edge identifier, source and target identifiers, a
typed edge kind, a pointer field label, acceptance, and an edge content
address. `root` edges originate at a run or batch pointer. `reference` edges
join two present object addresses. `missing-reference` edges retain a typed
relationship whose target cannot be resolved.

Graph construction reads the existing storage audit and only parses accepted
object JSON to discover typed object references. It does not mutate the store,
repair a missing object, quarantine an orphan, or replay a run. File ordering,
node ordering, edge numbering, breadth-first traversal, filters, and exports
are deterministic.

## CLI

Build the full graph or select a bounded page:

```powershell
glio-noncode storage-lineage --data-root .glio --output storage-lineage.json
glio-noncode storage-lineage --data-root .glio --resource edges --edge-kind reference --output references.json
glio-noncode storage-lineage --data-root .glio --root-only --output roots.json
glio-noncode storage-lineage --data-root .glio --format nodes-csv --output nodes.csv
glio-noncode storage-lineage --data-root .glio --format edges-csv --output edges.csv
glio-noncode storage-lineage --data-root .glio --format markdown --output storage-lineage.md
```

Filtered output is JSON so the query contract remains explicit. `--resource`
is `nodes` or `edges`. Node filters include `--node-kind`, `--root-only`,
`--orphan-only`, and `--missing-only`; edge filters include `--edge-kind` and
the same target-oriented orphan/missing filters. `--text`, `--offset`, and
`--limit` are bounded and deterministic.

Validate or compare saved graph documents without reopening the source store:

```powershell
glio-noncode storage-lineage-verify storage-lineage.json --output verified.json
glio-noncode storage-lineage-diff baseline.json candidate.json --output diff.json
glio-noncode storage-lineage-schema --output storage-lineage-schema.json
glio-noncode storage-lineage-capabilities --output storage-lineage-capabilities.json
```

## Observability

The observability projection emits one stable event for each node and edge and
sixteen aggregate metrics. Events classify accepted nodes and edges, unresolved
references, orphan objects, and rejected graph elements. Metrics include root,
object, missing, orphan, reachability, degree, depth, and connected-component
counts.

```powershell
glio-noncode storage-lineage-observability --data-root .glio --output lineage-observability.json
glio-noncode storage-lineage-observability --data-root .glio --format events-csv --output lineage-events.csv
glio-noncode storage-lineage-observability --data-root .glio --format metrics-csv --output lineage-metrics.csv
glio-noncode storage-lineage-observability-schema --output lineage-observability-schema.json
glio-noncode storage-lineage-observability-capabilities --output lineage-observability-capabilities.json
```

The event projection is timestamp-free. Rebuilding it from an identical graph
produces identical event and metric addresses. Event queries accept event type,
kind, state, text, offset, and limit.

## Review queue

The review projection translates structural gaps into prioritized, non-mutating
recommendations:

| Issue | Default severity | Default disposition | Meaning |
| --- | --- | --- | --- |
| `missing-reference` | critical | reconcile | a persisted pointer names an absent address |
| `orphan-object` | high | inspect | an object has no root reachability |
| `rejected-node` | high | inspect | a node failed its acceptance contract |
| `rejected-edge` | high | inspect | an edge points to unresolved structure |
| `unreachable-node` | medium | monitor | a present node is outside the root closure |
| `empty-graph` | info | monitor | the storage root has no persisted provenance |

The queue is ordered by descending priority and then stable review identifier.
It does not apply any recommendation. The CLI supports JSON, CSV, Markdown,
issue, severity, disposition, text, priority, offset, and limit filters:

```powershell
glio-noncode storage-lineage-review --data-root .glio --output lineage-review.json
glio-noncode storage-lineage-review --data-root .glio --severity critical --output critical-review.json
glio-noncode storage-lineage-review --data-root .glio --format markdown --output lineage-review.md
glio-noncode storage-lineage-review-schema --output lineage-review-schema.json
glio-noncode storage-lineage-review-capabilities --output lineage-review-capabilities.json
```

## Exact-byte offline packet

`storage-lineage-packet` packages ten fixed UTF-8 artifacts and one manifest:

| Artifact | Path | Contents |
| --- | --- | --- |
| graph | `lineage/graph.json` | complete address-only graph |
| nodes | `lineage/nodes.csv` | node table |
| edges | `lineage/edges.csv` | edge table |
| summary | `lineage/summary.json` | aggregate graph, event, and review counts |
| schema | `lineage/schema.json` | graph schema |
| capabilities | `lineage/capabilities.json` | graph boundary declaration |
| observability | `lineage/observability.json` | events and metrics |
| events | `lineage/events.csv` | event table |
| review | `lineage/review-queue.json` | prioritized review queue |
| review-table | `lineage/review.csv` | review table |

The manifest is `manifest.json`. Each artifact records its byte count, line
count, media type, source graph address, and exact byte address. The writer uses
atomic sibling replacement and refuses nonempty destinations unless
`--allow-existing` is supplied. The verifier rejects missing, unexpected,
unsafe, symlinked, duplicate, or tampered paths; manifest drift; invalid graph,
observability, or review identity; and prohibited public metadata.

```powershell
glio-noncode storage-lineage-packet --data-root .glio --destination lineage-packet --output packet.json
glio-noncode storage-lineage-packet-verify lineage-packet --output packet-verification.json
glio-noncode storage-lineage-packet-load lineage-packet --output packet-offline.json
glio-noncode storage-lineage-packet-schema --output packet-schema.json
glio-noncode storage-lineage-packet-capabilities --output packet-capabilities.json
```

Offline load is gated by exact verification. A failed packet cannot be
rehydrated as trusted graph state. The loaded value includes the graph,
observability, review queue, manifest, and verification receipt, all linked by
content addresses.

## HTTP service

The same boundary is available under `/v1/storage/lineage`:

- `GET /v1/storage/lineage` builds and pages the graph;
- `GET /v1/storage/lineage/nodes.csv` and `/edges.csv` export tables;
- `GET /v1/storage/lineage/schema` and `/capabilities` describe the graph;
- `GET /v1/storage/lineage/observability` returns or pages events;
- `GET /v1/storage/lineage/observability/events.csv` and `/metrics.csv` export observations;
- `GET /v1/storage/lineage/review` builds and pages review items;
- `GET /v1/storage/lineage/packet` builds packet metadata;
- `GET /v1/storage/lineage/packet/schema` and `/capabilities` describe packet guarantees;
- `POST /v1/storage/lineage/verify`, `/query`, and `/diff` operate on supplied graph documents;
- `POST /v1/storage/lineage/observability/query` and `/review/query` operate offline on supplied projections;
- `POST /v1/storage/lineage/packet/verify` verifies a packet directory.

All graph, observation, review, and packet responses are aggregate or
address-only. No endpoint in this surface returns source object payloads or
performs a storage mutation.
