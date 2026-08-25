# D15 Workbench Release Closure Operations

The workbench-release closure is the independent handoff layer for the D15
C13–C16 public aggregate release. It consumes the existing 56-artifact offline
bundle and publishes address-only projections. It does not add identity-level
fields, mutate source artifacts, or depend on a producer process remaining
running.

## Closure contract

The closure conserves these denominators:

| Plane | Count | Projection |
| --- | ---: | --- |
| source artifacts | 56 | artifact manifest and exact paths |
| public records | 16 | four operations, positive/control roles |
| executions | 16 | one execution per record |
| evaluation checks | 80 | five checks per record |
| validation cells | 80 | five cells per record |
| evidence cells | 16 | one input/output receipt per record |
| lineage edges | 52 | five source joins plus 16 record joins |
| views | 16 | one public view per record |
| review queue | 12 | one row for every control issue |
| diagnostics | 16 | one diagnostic per record |
| source runtime stages | 49 | contiguous stage ordinals 1 through 49 |

Every derived row is assigned a deterministic content address. The closure
boundary checks artifact paths, hydrated JSON shape, key inventory, address
presence, and the aggregate-only policy. The public surface intentionally
excludes direct identity fields and attribution metadata.

## Independent planes

The implementation is split into focused projections under
`glio_noncode.workbench_release_frontier_offline_closure_*`:

- boundary: validates public keys, artifact paths, and source handoff shape;
- indexes: creates ten bounded lookup indexes for artifacts, records,
  operations, checks, sources, stages, lineage, priority, capability, and
  diagnostic severity;
- query: provides bounded JSON, CSV, and Markdown views over every row family;
- reconciliation: joins denominators independently and emits 44 addressed
  checks plus deterministic bundle diffs;
- summary: reports operation, state, severity, queue, issue, and runtime
  counters;
- certification: issues ten domains and 60 evidence-linked checks;
- observability: records 184 ordered lifecycle events and 24 metrics;
- graph: builds a 404-node connected dependency graph with addressed edges;
- schema: declares required row fields and audits every projection shape;
- failure controls: applies twelve negative controls for omission, drift,
  forbidden keys, broken joins, queue gaps, runtime gaps, and release rejection;
- runtime: executes a fourteen-stage deterministic closure pipeline;
- export: writes fourteen exact-byte JSON artifacts and a verified manifest.

## CLI workflow

First materialize the source bundle:

```powershell
glio-noncode workbench-release-offline-bundle --destination workbench-release-bundle
```

Then inspect the independent closure:

```powershell
glio-noncode workbench-release-offline-bundle-closure-boundary workbench-release-bundle
glio-noncode workbench-release-offline-bundle-closure-indexes workbench-release-bundle
glio-noncode workbench-release-offline-bundle-closure-reconciliation workbench-release-bundle --format markdown
glio-noncode workbench-release-offline-bundle-closure-summary workbench-release-bundle --format csv
glio-noncode workbench-release-offline-bundle-closure-certification workbench-release-bundle
glio-noncode workbench-release-offline-bundle-closure-observability workbench-release-bundle
glio-noncode workbench-release-offline-bundle-closure-failures workbench-release-bundle
glio-noncode workbench-release-offline-bundle-closure-graph workbench-release-bundle
```

Run the full deterministic pipeline and export packet:

```powershell
glio-noncode workbench-release-offline-bundle-closure-runtime
glio-noncode workbench-release-offline-bundle-closure-export --destination workbench-release-closure-export
glio-noncode workbench-release-offline-bundle-closure-export-verify workbench-release-closure-export
```

## HTTP surface

The service exposes the same projections beneath
`/v1/workbench-release/bundle/`:

`closure-query`, `closure-schema`, `closure-boundary`, `closure-indexes`,
`closure-reconciliation`, `closure-summary`, `closure-certification`,
`closure-observability`, `closure-runtime`, `closure-failures`,
`closure-graph`, and `closure-export`.

The query surface accepts `resource`, `operation`, `role`, `state`,
`capability`, `priority`, `severity`, `stage_id`, `q`, `offset`, and `limit`.
The runtime route returns the public bundle summary plus every closure stage;
it does not return source payloads outside the existing aggregate boundary.

## Verification expectations

The focused test module verifies boundary and index conservation, query
filters, reconciliation, summary, 100% certification, 184 events, graph
connectivity, all twelve negative controls, fourteen-stage replay stability,
exact-byte export, CLI commands, and live HTTP routes. CI runs this focused
suite after the source D15 offline bundle suite.
