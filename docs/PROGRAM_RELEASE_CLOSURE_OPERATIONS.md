# D01-D16 program release closure

The program release closure is the top-level public aggregate handoff for
`glio-noncode`. It is a projection over the accepted architecture-program
offline bundle. It does not execute domain runtimes a second time, does not
copy opaque source payloads into its public results, and does not add identity,
attribution, model, or private subject metadata.

The implementation is split into small assurance planes. Each plane has a
typed result, a content address, a deterministic denominator, and an
inspectable failure state. The runtime composes the planes into one fourteen
stage report.

## Scope and source contract

The source handoff remains the lower-level transport contract. A release
closure caller may pass an existing `ProgramRuntimeOfflineBundle` to every
builder and runtime entry point. If no source bundle is passed, the builder
creates one using the current public aggregate architecture-program runtime.

The source handoff contributes these conserved denominators:

| Source measure | Required value | Meaning |
| --- | ---: | --- |
| Domain operations | 16 | One accepted receipt per D01-D16 |
| Program checks | 172 | Program-level evaluation checks |
| Quality checks | 18 | Quality and release quality checks |
| Runtime stages | 12 | Source runtime stage projection |
| Release artifacts | 11 | Original release projection subset |
| Domain artifact total | 98 | Sum of domain contribution counts |
| Evaluation check total | 7,178 | Sum of domain evaluation checks |
| Stage total | 380 | Sum of domain runtime stages |
| Offline artifacts | 18 | Complete portable source inventory |

The closure does not silently change these values. Reconciliation rejects a
projection when any source denominator or aggregate denominator is missing or
changed.

## Domain registry

The domain registry is ordered by dependency order. Source receipts remain the
authority for domain names, source runtime addresses, source receipt
addresses, stage counts, evaluation counts, artifact contributions, runtime
state, and acceptance.

| ID | Domain | Public release responsibility |
| --- | --- | --- |
| D01 | Variant Identity & Intake | Normalize variant identity and intake context |
| D02 | Structural Variation, Copy Number & Haplotype | Represent structural and haplotype variation |
| D03 | Specimen, Origin & Lineage | Preserve specimen origin and lineage aggregates |
| D04 | Reference & Annotation Governance | Control reference and annotation policy |
| D05 | Glioma Regulatory Atlas | Assemble regulatory atlas aggregates |
| D06 | Sequence Grammar & Variant Effect | Evaluate sequence grammar and effects |
| D07 | Chromatin, Accessibility & Methylation | Harmonize chromatin and methylation evidence |
| D08 | Cell State, Disease Class & Territory | Resolve cell-state and disease territory |
| D09 | 3D Genome & Regulatory Topology | Represent topology and regulatory neighborhoods |
| D10 | Variant-Element-Gene Linking | Link variants, elements, and genes |
| D11 | Causal Chain & Regulatory Driver Inference | Project causal regulatory chains |
| D12 | Cohort, Clonal & Longitudinal Discovery | Support cohort and longitudinal aggregates |
| D13 | Functional Validation & Experiment Design | Plan and validate experiments |
| D14 | Evidence Graph, Review & Reclassification | Maintain reviewable evidence relationships |
| D15 | Research Workbench & Collaboration | Provide workbench-ready aggregate projections |
| D16 | Agentic Platform, Quality & Deployment | Coordinate quality and deployment controls |

The word “Agentic” above is part of the domain’s product name from the source
domain registry. It is not attribution metadata. Generated closure artifacts
do not include agent identity, model identity, language identity, or author
fields.

## Aggregate closure denominators

The closure snapshot has an explicit, fixed shape:

| Resource | Count | Addressing rule |
| --- | ---: | --- |
| Domains | 16 | `program-release-domain:<sha256>` |
| Portable artifacts | 18 | `program-release-closure-artifact:<sha256>` |
| Dependencies | 120 | Complete forward DAG over sixteen ordered domains |
| Gates | 96 | Six gates for every domain |
| Certification checks | 96 | Six independent checks for every domain |
| Runtime stages | 14 | Source, projection, assurance, replay, and finalization |
| Plan steps | 23 | Sixteen source steps plus seven closure steps |
| Observability events | 266 | 16 starts + 18 artifacts + 120 dependencies + 96 gates + 16 finalizations |
| Observability metrics | 96 | Six metrics per domain |
| Export artifacts | 15 | Fifteen exact UTF-8 JSON files plus a manifest |

Every record has an address derived from its public aggregate fields. The
snapshot address is derived from the ordered resource records and source
bundle address. Two projections from the same source bundle and identifiers
therefore have the same address.

## Gate model

Every domain receives the same six gates:

1. `bundle_accepted` verifies the source receipt is accepted.
2. `runtime_address` verifies the source runtime has an address.
3. `runtime_depth` requires a positive runtime stage count.
4. `evaluation_checks` requires a positive evaluation contribution.
5. `artifact_contribution` requires a positive artifact contribution.
6. `public_projection` requires an accepted or published source runtime state.

Gate records retain observed and expected values. A caller can inspect why a
domain is blocked without opening an opaque payload. Gate partitions are
checked again by certification and reconciliation.

## Runtime stages

`run_program_release_closure` accepts an optional source bundle. When supplied,
the source bundle is reused for the snapshot, reconciliation, summary, and
replay. This is the preferred API and server path.

| Stage | ID | Responsibility |
| ---: | --- | --- |
| 1 | source-bundle | Reuse or construct the source offline handoff |
| 2 | aggregate-snapshot | Project D01-D16 aggregate records |
| 3 | domain-registry | Register domain receipt contributions |
| 4 | artifact-registry | Index eighteen portable artifacts |
| 5 | dependency-dag | Materialize the 120 forward edges |
| 6 | release-gates | Evaluate the 96 domain gates |
| 7 | boundary | Enforce public aggregate and path policy |
| 8 | indexes | Build and audit address-only indexes |
| 9 | reconciliation | Compare source and closure denominators |
| 10 | summary | Publish source and aggregate counters |
| 11 | assurance | Certify, observe, graph, rehearse failures, and plan |
| 12 | replay | Build the same projection twice |
| 13 | finalize | Close the release only when all planes pass |
| 14 | public-state | Expose the final ready or blocked state |

The runtime state is `ready` only if every stage is ready and every assurance
plane passes. Any stage can be inspected through the runtime report’s stage
address and detail fields.

## Address indexes and bounded queries

The index builder never copies source payload bytes. It creates sorted lookup
entries for domain IDs, artifact references, dependency IDs, gate IDs, resource
content addresses, source addresses, and domain runtime states.

`lookup_program_release_index` performs exact key lookup. The index audit
checks all resource denominators, uniqueness constraints, source address
coverage, and snapshot acceptance.

The query surface supports `domains`, `artifacts`, `dependencies`, `gates`,
and `runtime`. Every query is bounded by an offset and limit. The default limit
is 50 and the maximum is 500. Filters are `domain_id`, `gate_type`, `state`,
`relation`, `accepted_only`, and `text`. Rows are sorted before pagination, so
the same source and filters produce the same page and content address.

## Reconciliation and summary

Reconciliation emits nineteen explicit checks. They cover source readiness,
source addresses, eight source denominators, six aggregate denominators, and
three contribution sums. The summary carries both closure counters and source
counters so a reviewer can see the relationship without joining separate
files.

The summary includes:

```text
domain_count=16
artifact_count=18
dependency_count=120
gate_count=96
program_check_count=172
quality_check_count=18
source_runtime_stage_count=12
release_artifact_count=11
domain_artifact_total=98
evaluation_check_total=7178
stage_total=380
```

`source_runtime_stage_count` is the twelve-stage offline projection, while
`stage_total` is the 380-stage sum across sixteen domain receipts.

## Certification

Certification produces six checks per domain:

| Plane | Required observation |
| --- | --- |
| Source acceptance | Source receipt accepted |
| Runtime address | Runtime address present |
| Runtime depth | Stage count greater than zero |
| Evaluation contribution | Evaluation count greater than zero |
| Artifact contribution | Artifact count greater than zero |
| Gate partition | Exactly six gates belong to the domain |

The accepted report has 96 checks and 100% coverage. Every check carries its
domain ID, plane, observed and expected values, references, and content
address.

## Observability and graph

Events are numbered from one and have stable event IDs. The sequence contains
domain starts, artifact indexing, dependency ordering, gate evaluation, and
domain finalization. Metrics cover six measurements per domain: runtime stage
count, evaluation checks, source artifacts, acceptance, gate count, and runtime
address presence.

The graph contains 251 nodes: one root, sixteen domains, eighteen artifacts,
120 dependency nodes, and 96 gate nodes. Root edges make the public graph
connected, while dependency nodes retain source and target domain edges. The
graph audit checks partition counts, node and edge uniqueness, connectivity,
and acceptance.

## Operational matrix

The operational matrix names the sixteen actions used to reach the closure:

| Phase | Operations |
| --- | --- |
| Ingest | load-source |
| Projection | register-domains, register-artifacts, order-dependencies |
| Assurance | evaluate-gates, audit-boundary, build-indexes, reconcile-denominators, run-negative-controls |
| Publication | build-summary, issue-certification, emit-observability, build-graph, publish-export |
| Planning | compile-plan |
| Verification | replay-projection |

Every operation retains its resource family, phase, prerequisite, input
address, output address, and acceptance. The matrix audit checks operation
identity, ordering, five resource families, address health, backwards-only
prerequisites, and phase coverage. It is included in the runtime assurance
report and is available directly through the Python API and the
`/v1/program-release/closure/operations` route.

## Joined reviewer views

Normalized resources are ideal for transport, but reviewers often need one row
per domain. `build_program_release_review_views` joins each domain with its
incoming and outgoing dependency counts, six gate results, source stage and
evaluation contributions, source artifact contribution, and runtime address.
The view is accepted only when all sixteen rows follow source order and every
row is ready. Its audit rechecks identity, order, address, gate, dependency,
and contribution conservation. The API exposes the same projection at
`/v1/program-release/closure/views`, and the CLI emits it with
`program-release-closure-views`.

## Negative controls

The failure-injection module runs twelve mutations and expects every one to be
rejected:

| Case | Mutation |
| --- | --- |
| missing-domain | Remove D16 |
| duplicate-domain | Duplicate D15 |
| missing-artifact | Remove one artifact |
| duplicate-artifact | Duplicate one artifact |
| unsafe-path | Insert `../unsafe.json` |
| failed-gate | Fail the D01 bundle gate |
| dependency-cycle | Reverse the first dependency order |
| forbidden-key | Insert a prohibited public metadata key |
| missing-address | Remove a domain receipt address |
| missing-source-address | Remove a source artifact address |
| gate-partition | Remove one gate |
| replay-nondeterminism | Change a replay address |

The controls do not mutate the original frozen snapshot. They construct
temporary dataclass replacements and report the observed rejection.

## Export packet

The export packet contains these exact JSON artifacts:

```text
snapshot.json
domains.json
artifacts.json
dependencies.json
gates.json
boundary.json
indexes.json
reconciliation.json
summary.json
certification.json
observability.json
graph.json
failures.json
plan.json
runtime.json
```

`manifest.json` is the inventory manifest and is not counted as one of the
fifteen artifacts. Each artifact is canonical UTF-8 JSON with a terminal
newline. Verification checks exact bytes, byte counts, content addresses,
missing paths, changed paths, unexpected paths, manifest count, and acceptance.

## Python, HTTP, and CLI surfaces

```python
from glio_noncode.program_runtime_offline_bundle import build_program_runtime_offline_bundle
from glio_noncode.program_release_closure_runtime import run_program_release_closure

source = build_program_runtime_offline_bundle()
report = run_program_release_closure(source_bundle=source)
assert report.accepted
```

The API caches one source bundle per `(bundle_id, run_id)` on the local server:

```text
GET /v1/program-release/closure
GET /v1/program-release/closure/query
GET /v1/program-release/closure/schema
GET /v1/program-release/closure/boundary
GET /v1/program-release/closure/indexes
GET /v1/program-release/closure/reconciliation
GET /v1/program-release/closure/summary
GET /v1/program-release/closure/certification
GET /v1/program-release/closure/observability
GET /v1/program-release/closure/graph
GET /v1/program-release/closure/failures
GET /v1/program-release/closure/plan
GET /v1/program-release/closure/runtime
GET /v1/program-release/closure/export
```

Equivalent CLI commands are:

```text
glio-noncode program-release-closure
glio-noncode program-release-closure-query --resource gates --domain-id D01
glio-noncode program-release-closure-schema
glio-noncode program-release-closure-boundary
glio-noncode program-release-closure-indexes
glio-noncode program-release-closure-reconciliation
glio-noncode program-release-closure-summary
glio-noncode program-release-closure-certification
glio-noncode program-release-closure-observability
glio-noncode program-release-closure-graph
glio-noncode program-release-closure-failures
glio-noncode program-release-closure-plan
glio-noncode program-release-closure-runtime
glio-noncode program-release-closure-export --destination ./release-closure
glio-noncode program-release-closure-export-verify ./release-closure
```

Commands return zero for accepted reports and two for blocked reports or
invalid input. JSON output is stable and contains only public aggregate
fields. Query parameters accept optional `bundle_id` and `run_id`; query
routes additionally accept bounded filters.

## Review checklist

Before publishing a closure, verify:

1. the source bundle is accepted;
2. the snapshot contains D01-D16 in order;
3. all 120 dependencies point forward;
4. every domain has six passing gates;
5. reconciliation passes all nineteen checks;
6. summary counters match source denominators;
7. certification reaches 96 checks and 100% coverage;
8. observability reaches 266 events and 96 metrics;
9. the graph has one connected component;
10. all twelve negative controls reject their mutations;
11. the plan has 23 contiguous steps;
12. replay addresses are equal; and
13. export verification finds no missing, changed, or unexpected files.

The focused test suite exercises every item in this checklist, including HTTP
cache behavior and exact-byte export verification.
