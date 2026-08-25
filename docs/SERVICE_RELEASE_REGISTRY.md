# Service release registry

The service-release registry is the top-level public handoff for glio-noncode.
It joins the certified capability catalog, architecture-program runtime,
operational trace, and D01-D16 program release snapshot into one deterministic
release object. The registry is deliberately aggregate-only: it carries
surface identities, counters, immutable addresses, checks, and exact-byte
release metadata. It does not carry case records or direct subject values.

The registry is a projection over the accepted `ServiceSurfaceSnapshot`. It is
not a second execution engine and it does not mutate the source snapshot. Each
row is immutable after addressing, and every query, audit, graph, and export
can be recomputed from the same source addresses.

## Surface contract

The registry has six ordered surfaces:

| Order | Surface | Category | Source |
| ---: | --- | --- | --- |
| 1 | `capability-certification` | certification | 256 certified capability rows |
| 2 | `architecture-program` | runtime | 16 architecture receipts |
| 3 | `operational` | operations | accepted operational trace |
| 4 | `program-release` | release | D01-D16 aggregate closure |
| 5 | `service-status` | health | compact service status |
| 6 | `public-boundary` | boundary | public projection safety status |

The ordering is part of the address contract. Surface four is the complete
D01-D16 aggregate: 16 domains, 18 portable source artifacts, 120 ordered
dependencies, and 96 domain gates. The registry does not flatten or rewrite
those values; it records the D01-D16 snapshot address and publishes selected
aggregate rows for service clients.

The fixed registry denominators are:

| Resource | Count |
| --- | ---: |
| Surfaces | 6 |
| Exact-byte artifacts | 13 |
| Forward surface dependencies | 15 |
| Promotion gates | 24 |
| Observability events | 78 |
| Observability metrics | 24 |
| Reviewer views | 5 |
| Runtime stages | 14 |
| Release-plan steps | 23 |
| Negative controls | 8 |

The denominators are intentionally explicit. A release is not accepted when a
row is silently omitted, duplicated, or moved to a different surface.

## Promotion gates

Every surface receives four gates:

1. `source_accepted` requires the source surface to be accepted.
2. `address_present` requires a non-empty immutable source address.
3. `row_denominator` requires a non-empty public row contribution.
4. `public_projection` requires a non-empty public service address.

The 24 gates are retained as typed rows with observed and expected values. A
registry is accepted only when all 24 gates pass. A failed gate remains part of
the diagnostic object and blocks the final runtime state; it is never removed
from a report to make a release appear ready.

## HTTP API

The API uses the cached service snapshot for the registry routes. The first
request builds the source snapshot and later requests for the same bundle ID
reuse the immutable registry object.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/v1/service-release` | Six-surface registry snapshot |
| GET | `/v1/service-release/query` | Bounded page over registry rows |
| GET | `/v1/service-release/schema` | Schema declaration and audit |
| GET | `/v1/service-release/indexes` | Address-only indexes and audit |
| GET | `/v1/service-release/reconciliation` | Source and registry reconciliation |
| GET | `/v1/service-release/summary` | Conserved source and registry counters |
| GET | `/v1/service-release/certification` | Surface certification checks |
| GET | `/v1/service-release/observability` | 78 events and 24 metrics |
| GET | `/v1/service-release/graph` | Connected release lineage graph |
| GET | `/v1/service-release/failures` | Eight structural negative controls |
| GET | `/v1/service-release/plan` | Dependency-ordered 23-step plan |
| GET | `/v1/service-release/views` | Five reviewer-oriented tables |
| GET | `/v1/service-release/runtime` | Fourteen-stage runtime report |
| GET | `/v1/service-release/export` | Exact-byte export packet manifest |
| GET | `/v1/service-release/handoff` | Durable 13-artifact handoff metadata packet |
| GET | `/v1/service-release/handoff/status?directory=...` | Compact verified handoff status |
| GET | `/v1/service-release/handoff/inspect?directory=...` | Manifest-only handoff inspection |
| GET | `/v1/service-release/handoff/verify?directory=...` | Independent filesystem verification |
| GET | `/v1/service-release/handoff/query?directory=...` | Bounded verified artifact query |
| GET | `/v1/service-release/handoff/diff?left_directory=...&right_directory=...` | Address-only handoff diff |
| GET | `/v1/service-release/handoff/replay?directory=...` | Deterministic verification replay |

Query accepts `resource`, `surface_id`, `state`, `relation`, `accepted`, `q`,
`offset`, and `limit`. The resource contract is bounded to `surfaces`,
`artifacts`, `dependencies`, and `gates`. `limit` must be between 1 and 500;
the response includes `total`, `offset`, `limit`, `items`, and `has_more`.

Examples:

```text
GET /v1/service-release/query?resource=surfaces&accepted=true
GET /v1/service-release/query?resource=artifacts&surface_id=program-release
GET /v1/service-release/query?resource=gates&surface_id=capability-certification&limit=4
GET /v1/service-release/summary?bundle_id=release-review-2026-08
GET /v1/service-release/runtime?bundle_id=release-review-2026-08&run_id=runtime-001
```

Invalid resources, duplicate query parameters, invalid booleans, and out of
range pagination are rejected at the HTTP boundary. The response does not
silently widen a query after a validation failure.

## Command line

Emit the compact registry snapshot:

```text
glio-noncode service-release --plane snapshot --output service-release.json
```

Run the bounded query surface:

```text
glio-noncode service-release --plane query --resource gates --accepted --limit 24 --output gates.json
glio-noncode service-release --plane query --resource artifacts --surface-id program-release --output program-artifacts.json
```

Run individual assurance planes:

```text
glio-noncode service-release --plane schema --output service-release-schema.json
glio-noncode service-release --plane indexes --output service-release-indexes.json
glio-noncode service-release --plane reconciliation --output service-release-reconciliation.json
glio-noncode service-release --plane summary --output service-release-summary.json
glio-noncode service-release --plane certification --output service-release-certification.json
glio-noncode service-release --plane observability --output service-release-observability.json
glio-noncode service-release --plane graph --output service-release-graph.json
glio-noncode service-release --plane failures --output service-release-failures.json
glio-noncode service-release --plane plan --output service-release-plan.json
glio-noncode service-release --plane views --output service-release-views.json
```

Run the complete staged runtime:

```text
glio-noncode service-release --plane runtime --run-id release-run-001 --output service-release-runtime.json
```

The runtime exits zero only when every stage is ready and all assurance planes
are accepted. It exits with a release-blocked status when any gate or audit
fails.

## Exact-byte export

The export plane emits 13 artifacts under safe relative paths. JSON artifacts
use canonical JSON plus one terminal newline. CSV and Markdown artifacts use
stable sorted columns and newline handling. Every artifact records:

- relative path;
- media type;
- byte count;
- line count in the registry metadata;
- exact content address in the export packet.

Write a packet to a directory:

```text
glio-noncode service-release --plane export --destination service-release-export --output export-packet.json
```

The destination contains a root `manifest.json` and namespaced surface files.
Verify it later without reopening the source service snapshot:

```text
glio-noncode service-release-export-verify service-release-export --output export-verification.json
```

The verifier rejects missing files, unexpected files, duplicate paths, parent
traversal, drive-qualified paths, altered bytes, invalid UTF-8, and public
boundary violations. It also verifies that the manifest lists the same path
set that exists on disk.

## Durable handoff

The handoff is the operational filesystem boundary above the in-memory
registry and the compatibility export. It retains the same thirteen aggregate
artifacts while adding stable artifact identifiers, surface IDs, source
addresses, required-artifact denominators, a schema version, a run ID, and a
manifest content address. Artifact payloads remain outside the manifest so a
consumer can inspect catalog metadata before reading bytes.

Build and verify it with:

```text
glio-noncode service-release-handoff --plane build --destination service-release-handoff --output service-release-handoff.json
glio-noncode service-release-handoff --plane status --directory service-release-handoff
glio-noncode service-release-handoff --plane inspect --directory service-release-handoff
glio-noncode service-release-handoff --plane verify --directory service-release-handoff
glio-noncode service-release-handoff --plane query --directory service-release-handoff --surface-id program-release
glio-noncode service-release-handoff --plane diff --directory service-release-handoff --right-directory service-release-handoff-next
glio-noncode service-release-handoff --plane replay --directory service-release-handoff
glio-noncode service-release-handoff-verify service-release-handoff
```

Writes use sibling temporary files, flush and sync each payload, and atomically
replace the target. A non-empty destination requires explicit
`--allow-existing`; no recursive deletion is performed. Verification rejects
missing or unexpected files, duplicate IDs and paths, unsafe paths,
symlinked parents, byte-count drift, line-count drift, content-address drift,
malformed JSON, forbidden public-boundary headers, and manifest denominator or
version drift. Queries verify the directory first and preserve a blocked state
in their result rather than presenting tampered metadata as accepted.

The API build route returns packet metadata only. Filesystem routes require an
explicit local `directory` parameter and never return artifact bytes through
the service surface. Diff compares artifact content addresses and separately
retains manifest identity changes; replay runs the verifier twice and requires
identical verification addresses.

## Address and replay model

The service snapshot address is the source anchor. The registry address is
derived from the bundle ID, service address, source surface address, surfaces,
artifacts, dependencies, gates, and aggregate acceptance. Child rows are
addressed independently before they enter the registry body.

The runtime performs two additional builds from the same source snapshot. The
first and second registry addresses must equal the runtime snapshot address.
The replay row retains all three addresses and a deterministic boolean. A
replay drift blocks the final `public-state` stage.

The runtime stages are:

1. source surface;
2. registry snapshot;
3. surface registry;
4. artifact registry;
5. dependency matrix;
6. promotion gates;
7. indexes;
8. reconciliation;
9. summary;
10. certification;
11. assurance bundle;
12. replay;
13. finalize;
14. public state.

Each stage has an input address, output address, state, detail, and child
content address. This lets a client identify the first failed transition
without parsing the whole release closure.

## Indexes and queries

The registry builds six address-only indexes:

- `by_surface_id` maps the six surface identities;
- `by_artifact_ref` maps the 13 exact-byte artifact references;
- `by_dependency_id` maps all 15 forward edges;
- `by_gate_id` maps all 24 promotion gates;
- `by_content_address` maps every child address;
- `by_state` maps accepted surfaces and passed gates.

Index values contain references and addresses only. They do not copy source
payloads. The index audit independently checks cardinality, key/reference
uniqueness, address ordering, and source acceptance propagation.

## Reconciliation and summary

Reconciliation compares the registry against the exact `ServiceSurfaceSnapshot`
that produced it. It checks source address identity, source acceptance, all four
registry denominators, D01-D16 source identity, source address presence, unique
export paths, and gate-state propagation.

The summary retains both registry and source denominators. This makes it
possible for an offline reviewer to see that a six-surface registry contains a
256-row capability source, a 16-receipt architecture source, an operational
trace, and a 16-domain D01-D16 source without reopening the source runtime.

## Observability and views

Each surface receives the same 13-event sequence: source read, registration,
artifact addressing, dependency check, gate evaluation, index build, summary,
certification, graph, plan, view, boundary, and release readiness. The result
is 78 ordered events with unique event IDs and 24 surface metrics.

The five views are:

1. surface matrix;
2. exact-byte artifact matrix;
3. promotion gate matrix;
4. promotion summary;
5. dependency order.

Views contain only aggregate rows and retain the source surface IDs used to
build them. The view audit checks row closure and acceptance for every table.

## Negative controls

Eight controls demonstrate that the registry fails closed:

- missing surface;
- duplicate artifact path;
- missing gate;
- reversed dependency order;
- blank source address;
- forbidden public metadata key;
- unsafe export path;
- replay address drift.

Each control stores the mutation description, expected failure class, observed
failure class, and a pass boolean. A negative-control report is accepted when
all eight controls produce their expected failure class.

## Public boundary

All registry contracts pass recursive key and token checks before release
addressing. The policy rejects attribution, model, language, identity, direct
contact, and direct subject fields from runtime projections. Schema declarations
may describe input shapes in their own schema plane, but the service-release
registry itself contains aggregate release values only.

The service snapshot, registry, and durable handoff are included in the
repository-wide `public-surface-audit`. The inventory now certifies 35 named
projections, including the service-release snapshot, schema, default bounded
query, handoff metadata packet, authenticated deployment profile/schema, and
versioned reference manifest/schema.

## Performance and caching

The API caches one service snapshot on the server and one registry snapshot per
bundle ID. Queries operate on immutable rows and do not rebuild source domain
runtimes. Runtime and export requests reuse the cached service snapshot, so
the expensive source handoff is built once per server process.

CLI commands intentionally build a fresh local snapshot for reproducibility.
Use the runtime command once when a complete closure is needed, then use the
export verifier for repeated filesystem checks.

## Verification checklist

Before promoting a service release, run:

```text
python -m compileall -q src tests
python -m unittest tests.test_service_surface tests.test_service_release -q
python -m unittest tests.test_public_surface_audit -q
glio-noncode service-release --plane runtime --output /tmp/service-release-runtime.json
glio-noncode public-surface-audit --output /tmp/public-surface-audit.json
```

The focused service-release test suite covers source integration, cardinality,
queries, exact-byte artifacts, every assurance plane, replay, HTTP routes, CLI
outputs, and tamper detection. The repository-wide audit must remain accepted
after any addition to the public service surface.
