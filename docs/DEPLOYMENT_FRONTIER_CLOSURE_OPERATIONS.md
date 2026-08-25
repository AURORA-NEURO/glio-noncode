# D16 deployment frontier closure operations

The deployment frontier closure is the independent release-handoff plane for
the D16 C13-C16 deployment-governance source bundle. It turns the public
aggregate source projection into bounded, queryable, addressable review
evidence. Every closure row carries an address derived from the D16 bundle or
from the closure projection that consumes it.

## Scope and denominators

The source bundle contains 51 artifacts, 5 source receipts, 16 fixture
records, 16 executions, 80 evaluation checks, 64 validation cells, 16 derived
evidence rows, 52 lineage edges, 16 review views, 12 queue items, 13
diagnostics, 38 runtime stages, 32 audit events, 33 transcript events, and 37
trace observations. The closure also exposes 4 operation partitions, 12
control rows, and 12 structural failure probes.

| Resource | Meaning | Rows |
| --- | --- | ---: |
| `artifacts` | Source bundle artifact manifest | 51 |
| `records` | Fixture record expectations | 16 |
| `executions` | Observed execution results | 16 |
| `checks` | Evaluation checks | 80 |
| `sources` | Public source receipts | 5 |
| `validation` | Validation matrix cells | 64 |
| `evidence` | Record input/output address pairs | 16 |
| `edges` | Lineage relationships | 52 |
| `views` | Reviewer-facing record state | 16 |
| `queue` | Review queue items | 12 |
| `diagnostics` | Diagnostic findings | 13 |
| `stages` | Runtime stage observations | 38 |
| `stage_index` | Runtime stage lookup projection | 38 |
| `operations` | Operation partitions | 4 |
| `controls` | Negative/control record projection | 12 |
| `failures` | Structural failure probes | 12 |
| `audit_events` | Audit event chain projection | 32 |
| `transcript_events` | Runtime transcript projection | 33 |
| `trace_observations` | Runtime trace projection | 37 |

## Independent closure planes

- Boundary auditing checks all 51 artifact payloads, safe relative paths,
  canonical addresses, public source URIs, unique identities, recursive key
  policy, and accepted root state.
- Ten indexes provide address-only lookup by artifact, record, operation,
  check, source, stage, lineage edge, queue priority, issue code, and state.
- Reconciliation runs 47 checks across manifest, fixture, evaluation,
  validation, evidence, lineage, review, queue, diagnostics, runtime, event,
  policy, and release planes.
- Summary auditing exposes counters, per-operation partitions, state
  partitions, severity partitions, and 22 conservation checks.
- Certification evaluates 10 independent domains with 6 checks each, for 60
  checks and 100% local coverage when the source bundle is intact.
- Observability emits 151 lifecycle events and 24 deterministic metrics.
- The graph contains 599 nodes and 866 edges in one connected component.
- Failure rehearsal runs 12 structural negative controls and confirms each
  mutation is rejected by the intended boundary.
- Runtime executes 14 ordered stages, including source materialization,
  boundary, indexes, reconciliation, summary, certification, observability,
  graph, schema, failure controls, replay, and finalization.

## CLI workflow

Materialize the source bundle, then run the closure planes against that
directory:

```text
glio-noncode deployment-frontier-offline-bundle --destination deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-closure-query deployment-frontier-bundle --resource records --operation privacy_security_policy
glio-noncode deployment-frontier-offline-bundle-closure-boundary deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-closure-indexes deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-closure-reconciliation deployment-frontier-bundle --format markdown
glio-noncode deployment-frontier-offline-bundle-closure-summary deployment-frontier-bundle --format csv
glio-noncode deployment-frontier-offline-bundle-closure-certification deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-closure-observability deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-closure-failures deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-closure-graph deployment-frontier-bundle
glio-noncode deployment-frontier-offline-bundle-closure-runtime --run-id deployment-frontier-closure-runtime
glio-noncode deployment-frontier-offline-bundle-closure-export --destination deployment-frontier-closure-export
glio-noncode deployment-frontier-offline-bundle-closure-export-verify deployment-frontier-closure-export
```

The export command writes 14 canonical UTF-8 JSON artifacts and
`manifest.json`. Verification compares exact bytes, expected content
addresses, missing paths, changed paths, and unexpected paths. It returns a
nonzero process status if any comparison fails.

## HTTP workflow

The dependency-free service exposes the same closure decisions under
`/v1/deployment-frontier/bundle`. Query parameters include `bundle_id`,
`run_id`, `resource`, `operation`, `role`, `state`, `capability`, `priority`,
`severity`, `stage_id`, `text`, `offset`, and `limit`. The public endpoints are:

```text
GET /v1/deployment-frontier/bundle/closure-query
GET /v1/deployment-frontier/bundle/closure-schema
GET /v1/deployment-frontier/bundle/closure-boundary
GET /v1/deployment-frontier/bundle/closure-indexes
GET /v1/deployment-frontier/bundle/closure-reconciliation
GET /v1/deployment-frontier/bundle/closure-summary
GET /v1/deployment-frontier/bundle/closure-certification
GET /v1/deployment-frontier/bundle/closure-observability
GET /v1/deployment-frontier/bundle/closure-runtime
GET /v1/deployment-frontier/bundle/closure-failures
GET /v1/deployment-frontier/bundle/closure-graph
GET /v1/deployment-frontier/bundle/closure-export
```

## Release gate

The closure is accepted only when the source bundle is accepted, all
reconciliation checks pass, all ten certification domains pass, the summary
and schema audits conserve their denominators, the graph is connected, all
failure controls behave as expected, and deterministic replay produces the
same source address. These are local evidence gates; they do not substitute
for institutional deployment approval or external validation.
