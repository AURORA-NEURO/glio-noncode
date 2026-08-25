# Architecture program offline operations

The architecture program executes sixteen canonical domain runtimes and
already exposes a report, runtime, release, replay, and operational trace.
This handoff adds a transport boundary for those projections. It is designed
for a reviewer or a second process that has the bundle directory but does not
have the producer runtime, object store, or network service.

The bundle is public aggregate data only. It does not contain direct subject
identifiers, contact fields, credentials, agent or model metadata, or
programming-language attribution. The runtime is research infrastructure and
does not make clinical, diagnostic, treatment, or patient-level claims.

## Closed denominators

Every default build closes the following denominators:

| Plane | Count |
| --- | ---: |
| Canonical domain operations | 16 |
| Program checks | 172 |
| Quality checks | 18 |
| Source runtime stages | 12 |
| Source release projections | 11 |
| Portable handoff artifacts | 18 |
| Certification domains | 7 |
| Certification checks | 36 |

The portable artifacts retain the eleven existing release projections and add
operational, domain-operation, stage, quality, release-check, specification,
and capability projections. JSON artifacts are canonicalized before hashing;
CSV and Markdown artifacts are hashed over the exact UTF-8 bytes written.

## Materialize and verify

```powershell
glio-noncode architecture-program-offline-bundle `
  --destination architecture-program-bundle `
  --bundle-id architecture-program-public-bundle `
  --run-id architecture-program-offline-runtime

glio-noncode architecture-program-offline-verify `
  architecture-program-bundle `
  --output architecture-program-verification.json
```

`bundle.json` contains the root identity, relative artifact paths, media
types, byte and line counts, artifact addresses, and independent build checks.
The verifier reads the manifest and files only. It checks exact bytes,
manifest reconstruction, path closure, duplicate identities, public keys,
and declared denominators. Extra files, missing files, tampered bytes, and
address drift cause a blocked result.

## Query and inspection

Queries are bounded and carry their own content address. Supported resources
are `artifacts`, `domains`, `operations`, `checks`, `stages`, `quality`,
`release_checks`, `specifications`, `capabilities`, and `states`.

```powershell
glio-noncode architecture-program-offline-query architecture-program-bundle `
  --resource domains --domain-id D08 --accepted-only

glio-noncode architecture-program-offline-query architecture-program-bundle `
  --resource checks --limit 500 --format csv --output program-checks.csv

glio-noncode architecture-program-offline-boundary architecture-program-bundle
glio-noncode architecture-program-offline-boundary architecture-program-bundle --key-inventory
glio-noncode architecture-program-offline-indexes architecture-program-bundle
glio-noncode architecture-program-offline-observability architecture-program-bundle --format metrics-csv
```

Indexes are address-only. They cover artifact ID, path, domain ID, check ID,
stage ID, and observed domain state without duplicating payload bytes. The
boundary command reports recursive key inventory and relative-path checks.

## Reconciliation and certification

```powershell
glio-noncode architecture-program-offline-audit architecture-program-bundle
glio-noncode architecture-program-offline-reconciliation architecture-program-bundle --format markdown
glio-noncode architecture-program-offline-summary architecture-program-bundle --format markdown
glio-noncode architecture-program-offline-certification architecture-program-bundle --format markdown
glio-noncode architecture-program-offline-runtime --output program-offline-runtime.json
```

Reconciliation joins the runtime root to the manifest, the report to domain
operation rows, checks to their CSV export, source stages to the stage
projection, quality to its checks, release checks to their export, and the
specification and capability catalogs to the sixteen-domain denominator.

Certification separates the handoff into seven independent domains:

1. manifest identity and lifecycle;
2. artifact inventory and byte accounting;
3. runtime denominator and stage closure;
4. release projection closure;
5. cross-artifact identity joins;
6. offline query resource closure; and
7. the public aggregate boundary.

Observability adds a timestamp-free lifecycle stream with two events per
offline stage (`stage.started` and `stage.completed`) plus twelve addressed
aggregate metrics for artifacts, bytes, lines, domains, checks, stages,
warnings, and acceptance. Event and metric CSV exports contain no opaque
payloads and are reproducible from the bundle alone.

The staged offline runtime performs materialization, exact-byte audit, public
boundary audit, index build and audit, reconciliation, summary audit,
certification, observability, deterministic replay, and finalization. Two
builds with the same bundle and run IDs must produce the same root address.

## HTTP surface

When the local service is running, the same projections are available under:

```text
GET /v1/architecture/offline/bundle
GET /v1/architecture/offline/query?resource=domains&domain_id=D08
GET /v1/architecture/offline/schema
GET /v1/architecture/offline/audit
GET /v1/architecture/offline/boundary
GET /v1/architecture/offline/indexes
GET /v1/architecture/offline/reconciliation
GET /v1/architecture/offline/summary
GET /v1/architecture/offline/runtime
GET /v1/architecture/offline/certification
GET /v1/architecture/offline/observability
```

Related requests reuse one immutable in-process bundle for the selected
bundle/run identity, so query, audit, summary, and certification requests do
not rebuild the sixteen domain runtimes repeatedly. The cache is scoped to
the service process; a new process rebuilds from the deterministic public
fixture.

## Failure behavior

The handoff never turns an incomplete source runtime into an accepted bundle.
Failed source checks, missing artifacts, malformed JSON, forbidden keys,
unsafe paths, changed bytes, non-contiguous stages, denominator drift, and
non-deterministic replay leave explicit failed checks in the result. A
consumer can inspect those checks without trusting a producer-side database.
