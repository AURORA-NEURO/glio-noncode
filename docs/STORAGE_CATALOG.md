# Storage catalog and offline index

The storage catalog is the normalized read model for the local content-addressed
store. It is built from the store-wide storage audit and is intentionally
separate from the audit itself:

| Plane | Responsibility | Can mutate the store | Contains object payloads |
| --- | --- | ---: | ---: |
| Storage audit | Establish byte, hash, pointer, replay, reachability, and filesystem integrity | No | No |
| Storage catalog | Normalize audit rows and provide deterministic indexes and bounded queries | No | No |
| Catalog observability | Explain row states and index coverage with stable events and metrics | No | No |
| Catalog packet | Move an exact-byte catalog review set between isolated environments | No | No |

The catalog is suitable for local operator tooling, review queues, release
assurance, and offline handoff. It is not a replacement for the object store,
does not reconstruct missing objects, and does not turn a warning into a valid
scientific result.

## Construction boundary

`build_storage_catalog` accepts either an already-built `StorageAuditReport` or
a `CaseRuntime`. A runtime input causes one read-only audit. A report input
allows a caller to reuse an audit that it has already accepted or retained for
comparison. Both paths produce the same catalog for the same report.

The catalog construction order is fixed:

1. Object audit rows are projected into `object:<address>` entries.
2. Missing addresses become `missing:<address>` entries.
3. Run audit rows become `run:<run_id>` entries.
4. Batch audit rows become `batch:<batch_id>` entries.
5. Unexpected relative filesystem paths become `unexpected:<path>` entries.
6. Entries are sorted by their stable entry identifier.
7. Address, path, kind, and state indexes are rebuilt from the sorted entries.
8. The catalog body is content-addressed after all derived rows are closed.

No entry contains the object JSON that was read during the audit. The
`target_address` field is a reference only. The `byte_count` field reports the
audited object file size and is not a byte payload. Run and batch rows expose
their pointer presence and warning count, not their index documents.

## Entry kinds

### Object

An object row represents a validly-shaped `objects/<sha256>.json` candidate in
the audit. `resource_key` and `target_address` are the same content address.
The `path` is normalized to `objects/<digest>.json`. An object that is present
but unreachable is retained with `state=orphan` and `accepted=false`, even when
its JSON and filename hash are individually valid.

### Missing

A missing row represents a referenced object address that was not found during
reachability closure. It has `accepted=false`, `referenced=true`, and a stable
`resource_key`. A canonical SHA-256 address also receives the expected object
path; an address with a different scheme remains address-only and has no path.

### Run

A run row represents one persisted run index. Its `resource_key` is the run
identifier and its path is `runs/<filename>`. `referenced` means the run index
contains at least one object pointer. A rejected run remains visible with its
warning count so a caller can distinguish absence from a failed replay gate.

### Batch

A batch row represents one persisted batch index. Its `resource_key` is the
batch identifier and its path is `batches/<filename>`. `referenced` means an
input or result address is present. Batch reopen failures are represented by a
rejected row and are never hidden by catalog construction.

### Unexpected

An unexpected row represents a filesystem entry outside the audit's accepted
object, run, or batch file contract. The normalized relative path is both its
resource key and path. It is always rejected and gives the caller a stable
reason to stop a release or maintenance handoff.

## State model

The state value is intentionally orthogonal to the `accepted` boolean:

| State | Meaning | Accepted |
| --- | --- | ---: |
| `accepted` | Audit row passed and is reachable where reachability applies | Usually yes |
| `rejected` | Audit row exists but failed structural, hash, or replay checks | No |
| `orphan` | Object is valid enough to observe but unreachable from persisted roots | No |
| `missing` | A referenced address has no corresponding object file | No |
| `unexpected` | Filesystem entry is outside the accepted store contract | No |

The catalog's `accepted` flag is true only when the source audit is accepted and
every normalized entry is accepted. A catalog can still be queried when it is
rejected. This keeps blocked evidence inspectable while preventing accidental
promotion.

## Closed indexes

All indexes map a stable key to one or more sorted entry identifiers. A key is
stored once per index, even when many entries share it. Index rows are content
addressed independently and the enclosing catalog address commits to every row.

### Address index

The address index covers entries with a `target_address`, including present
objects and missing references. Run and batch entries are deliberately not
invented as addresses because their index files are not content-addressed
objects in the object store.

### Path index

The path index covers normalized object, run, batch, and unexpected paths, plus
canonical expected paths for missing SHA-256 object addresses. A path prefix
query uses this index before applying remaining filters.

### Kind index

The kind index has up to one row for each entry kind. Resource queries use this
index so callers can request `objects`, `runs`, `batches`, `missing`, or
`unexpected` without parsing the complete entry list themselves.

### State index

The state index has up to one row for each observed state. Exact state queries
are useful for release gates and maintenance review because `missing`, `orphan`,
and `unexpected` are different operational decisions.

## Query contract

`query_storage_catalog` accepts a typed catalog or a serialized catalog mapping.
It never scans the local store. Its arguments are:

| Argument | Values | Behavior |
| --- | --- | --- |
| `resource` | `entries`, `objects`, `runs`, `batches`, `missing`, `unexpected` | Selects the row universe |
| `kind` | Five entry kinds | Intersects with the kind index |
| `state` | Five states | Intersects with the state index |
| `prefix` | Bounded text | Matches address and path indexes case-insensitively |
| `text` | Bounded text | Searches the public normalized row |
| `accepted` | Boolean or null | Exact boolean filter |
| `referenced` | Boolean or null | Exact boolean filter |
| `offset` | Non-negative integer | Stable page origin |
| `limit` | 1 through 500 | Bounded page size |

The returned query receipt includes the normalized filters, total count, page
coordinates, selected index names, source catalog address, and its own content
address. A query result is not a new catalog snapshot and does not change the
catalog address.

The implementation first intersects exact kind/state/prefix candidates, then
applies resource, boolean, and text filters in entry order. The resulting page
is always a slice of the catalog's sorted entries. Repeating the same query over
the same catalog therefore produces identical bytes and addresses.

## Structural diffs

`diff_storage_catalog` compares entry content addresses and index row content
addresses. It reports:

- added entry identifiers;
- removed entry identifiers;
- changed entry identifiers whose normalized fields differ;
- added and removed index keys prefixed by index name;
- index names with changed row membership;
- whether derived counts changed.

Diff is an accepted comparison operation even when an input catalog is
rejected. The rejected input state remains visible in the source catalog
addresses; the diff does not erase or reinterpret it.

## Observability

`build_storage_catalog_observability` creates timestamp-free observations. Each
entry has a generic `entry-seen` event and a kind-specific event. Orphan and
rejected entries receive an additional explicit issue event. Each index row
receives an `index-built` event with the number of entry identifiers it covers.
Sequences start at one and are contiguous.

Metrics are sorted by name and include:

| Metric group | Examples |
| --- | --- |
| Row counts | entries, objects, missing, runs, batches, unexpected |
| Quality counts | accepted, rejected, orphan, warning total |
| Reachability | referenced entries, indexed entries |
| Index coverage | total rows, total keys, address/path/kind/state rows |
| Gate state | accepted catalog as 0 or 1 |

Observability queries page events by event type, state, and public text. Metrics
are aggregate counts with a `count` unit and `catalog` scope. No wall clock,
host name, process identifier, or arbitrary metadata is included, so two
observations over the same catalog are replayable.

## Exact-byte packet

`build_storage_catalog_packet` creates a fixed ten-artifact packet:

| ID | Path | Role |
| --- | --- | --- |
| `catalog-json` | `catalog/catalog.json` | Full normalized catalog |
| `entries-csv` | `catalog/entries.csv` | Entry table |
| `indexes-csv` | `catalog/indexes.csv` | Four index tables |
| `summary-json` | `catalog/summary.json` | Counts and source addresses |
| `schema-json` | `catalog/schema.json` | Contract declaration |
| `capabilities-json` | `catalog/capabilities.json` | Feature declaration |
| `observability-json` | `catalog/observability.json` | Timestamp-free observation |
| `events-csv` | `catalog/events.csv` | Observation event table |
| `metrics-csv` | `catalog/metrics.csv` | Observation metric table |
| `boundary-json` | `catalog/boundary.json` | Public boundary declaration |

The eleventh required file is `manifest.json`; it is metadata for the ten
payload artifacts and is not counted as a payload. Every artifact records its
relative path, media type, role, source catalog address, byte count, line
count, and exact-byte content address.

Packet writing is atomic per file. A destination must not be a symlink and must
be empty unless `allow_existing=true` is explicitly supplied. The writer never
removes existing files. The verifier rejects:

- missing manifest or payload files;
- unsafe or symlinked paths;
- duplicate artifact IDs or paths;
- unexpected files;
- byte, line, or artifact-address drift;
- invalid manifest counts, versions, or payload IDs;
- catalog or observability identity drift;
- public-boundary violations in JSON or text artifacts.

Offline loading is gated by successful verification. It hydrates only the typed
catalog and observation projections from the packet's JSON artifacts. CSV files
remain evidence exports and are not treated as authoritative input.

## CLI

Build a catalog from a local data root:

```text
glio-noncode storage-catalog --data-root .glio --output storage-catalog.json
glio-noncode storage-catalog --data-root .glio --kind object --format json --output objects.json
glio-noncode storage-catalog --data-root .glio --format entries-csv --output entries.csv
glio-noncode storage-catalog --data-root .glio --format indexes-csv --output indexes.csv
glio-noncode storage-catalog --data-root .glio --format markdown --output catalog.md
```

Produce the observation planes and contract documents:

```text
glio-noncode storage-catalog-observability --data-root .glio --format metrics-csv --output metrics.csv
glio-noncode storage-catalog-schema --output catalog-schema.json
glio-noncode storage-catalog-capabilities --output catalog-capabilities.json
glio-noncode storage-catalog-observability-schema --output observation-schema.json
glio-noncode storage-catalog-observability-capabilities --output observation-capabilities.json
```

Create and verify a fixed offline packet:

```text
glio-noncode storage-catalog-packet --data-root .glio --destination catalog-packet
glio-noncode storage-catalog-packet-verify catalog-packet --output verification.json
glio-noncode storage-catalog-packet-load catalog-packet --output hydrated.json
glio-noncode storage-catalog-packet-schema --output packet-schema.json
glio-noncode storage-catalog-packet-capabilities --output packet-capabilities.json
```

The verify and load commands return a nonzero status for rejected packets. A
rejected catalog itself can still be emitted and queried for triage.

## HTTP surface

The HTTP service exposes the same projections without changing their
determinism:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/v1/storage/catalog` | Build and page a live catalog |
| GET | `/v1/storage/catalog/schema` | Return the catalog schema |
| GET | `/v1/storage/catalog/capabilities` | Return catalog capabilities |
| GET | `/v1/storage/catalog/entries.csv` | Export entries |
| GET | `/v1/storage/catalog/indexes.csv` | Export indexes |
| POST | `/v1/storage/catalog/verify` | Verify a supplied catalog |
| POST | `/v1/storage/catalog/query` | Query a supplied catalog |
| POST | `/v1/storage/catalog/diff` | Diff two supplied catalogs |
| GET | `/v1/storage/catalog/observability` | Build or page observations |
| GET | `/v1/storage/catalog/observability/schema` | Return observation schema |
| GET | `/v1/storage/catalog/observability/capabilities` | Return observation capabilities |
| GET | `/v1/storage/catalog/observability/events.csv` | Export events |
| GET | `/v1/storage/catalog/observability/metrics.csv` | Export metrics |
| POST | `/v1/storage/catalog/observability/query` | Query supplied observations |
| GET | `/v1/storage/catalog/packet` | Build packet metadata |
| GET | `/v1/storage/catalog/packet/schema` | Return packet schema |
| GET | `/v1/storage/catalog/packet/capabilities` | Return packet capabilities |
| POST | `/v1/storage/catalog/packet/verify` | Verify a packet directory |

GET catalog filters use the same names as the query contract. Boolean filters
are supplied as `true` or `false`. POST routes accept a closed object with the
source projection and a `query` object where applicable. Error responses retain
the service's existing validation boundary and never include source payloads.

## Failure handling

Catalog construction fails closed for invalid typed contracts, unsorted or
duplicate index rows, unknown row references, unsupported query values, and
contract size limits. It does not catch or downgrade a malformed source audit;
the audit's accepted flag and warning state are carried forward.

Packet verification is deliberately stricter than packet construction. A
packet can be generated from a rejected catalog for diagnosis, but offline
hydration requires an accepted manifest, a valid catalog identity, a valid
observation identity, exact artifact bytes, expected paths, and a clean public
boundary. This gives review tooling a complete failure receipt rather than a
partial success signal.

## Extension rules

Future catalog changes should preserve these invariants:

1. New fields must be added to the schema and content-addressed body together.
2. New entry kinds require a state mapping, index behavior, CSV behavior,
   observability event, packet coverage, CLI behavior, and focused tests.
3. New indexes require a closed name, row identity, query semantics,
   observability metric, CSV coverage, and packet coverage.
4. Payload-bearing fields are not permitted in the public catalog boundary.
5. Timestamps and host/process metadata are not permitted in deterministic
   catalog or observation bodies.
6. Every new packet artifact changes the fixed denominator and must update the
   manifest, schema, capability projection, verifier, CLI, and CI checks.
7. A rejected source remains queryable but cannot silently become accepted.
8. All public mappings reject unknown fields so drift is visible at the input
   boundary.

## Verification matrix

The focused test module covers the complete catalog lifecycle:

| Area | Coverage |
| --- | --- |
| Construction | Empty, populated, object, run, batch, missing, orphan, unexpected |
| Indexes | Exact kind/state, resource selection, address prefix, path prefix |
| Query | Text, accepted, referenced, pagination, unsupported values, bounds |
| Integrity | Content-address round trips, unknown fields, tampered rows, diffs |
| Observability | Deterministic events, metric totals, identity, query paging, CSV |
| Packets | Fixed denominator, atomic output, exact bytes, identity, offline load |
| Packet failure | Tamper, missing, extra, unsafe, nonempty destination |
| Public surfaces | CLI commands, HTTP GETs, HTTP POST query, schemas, capabilities |

CI runs the focused test module alongside the existing audit, maintenance,
lineage, and public-surface tests. This keeps the catalog's independent
read-model guarantees visible whenever the store or public API changes.
