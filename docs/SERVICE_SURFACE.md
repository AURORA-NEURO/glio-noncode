# Local service surface

The local service exposes the certified product surfaces through a dependency-free
HTTP API. The service constructs one deterministic snapshot lazily and reuses it
for the lifetime of the server. Every projection carries the address of the
report or runtime from which it was derived.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Cheap process health response |
| GET | `/v1/schema` | Existing case contract summary |
| GET | `/v1/public-surface/audit` | Audit the complete repository-wide public service and bundle projection inventory |
| GET | `/v1/cohort/benchmark/schema` | Return the aggregate cohort benchmark schema |
| GET | `/v1/cohort/benchmark/capabilities` | Return split, leakage, calibration, selective-risk, and transport capabilities |
| POST | `/v1/cohort/benchmark` | Run a bounded aggregate cohort benchmark report from declared records and configuration |
| GET | `/v1/review-workspace/schema` | Return the provenance-first review workspace schema |
| GET | `/v1/review-workspace/capabilities` | Return operational review workspace capabilities |
| GET | `/v1/review-workspace/query/schema` | Return bounded review-workspace query and facet schema |
| GET | `/v1/review-workspace/query/capabilities` | Return deterministic query, pagination, and facet capabilities |
| GET | `/v1/review-workspace/plan/schema` | Return the ordered review-workspace triage-plan schema |
| GET | `/v1/review-workspace/plan/capabilities` | Return triage-plan ordering, dependency, and boundary capabilities |
| GET | `/v1/review-workspace/plan/execution/schema` | Return the append-only review-plan execution schema |
| GET | `/v1/review-workspace/plan/execution/capabilities` | Return execution replay, dependency, and boundary capabilities |
| GET | `/v1/service-release` | Build the six-surface public service-release registry |
| GET | `/v1/service-release/query` | Query service surfaces, artifacts, dependencies, or gates |
| GET | `/v1/service-release/schema` | Return the service-release schema and boundary audit |
| GET | `/v1/service-release/indexes` | Return six address-only registry indexes and their audit |
| GET | `/v1/service-release/reconciliation` | Reconcile registry and cached service snapshot denominators |
| GET | `/v1/service-release/summary` | Return conserved source and registry counters |
| GET | `/v1/service-release/certification` | Return surface certification checks |
| GET | `/v1/service-release/observability` | Return 78 deterministic registry events and 24 metrics |
| GET | `/v1/service-release/graph` | Return the connected registry lineage graph |
| GET | `/v1/service-release/failures` | Return eight registry negative controls |
| GET | `/v1/service-release/plan` | Return the 23-step service-release plan |
| GET | `/v1/service-release/views` | Return five reviewer-oriented registry views |
| GET | `/v1/service-release/runtime` | Run the fourteen-stage registry runtime and replay gate |
| GET | `/v1/service-release/export` | Return the exact-byte service-release packet manifest |
| GET | `/v1/service-release/handoff` | Build durable service-release handoff metadata |
| GET | `/v1/service-release/handoff/status?directory=...` | Verify and return handoff status |
| GET | `/v1/service-release/handoff/inspect?directory=...` | Inspect handoff manifest metadata |
| GET | `/v1/service-release/handoff/verify?directory=...` | Verify handoff files and boundaries |
| GET | `/v1/service-release/handoff/query?directory=...` | Query verified handoff artifacts |
| GET | `/v1/service-release/handoff/diff?left_directory=...&right_directory=...` | Compare handoff addresses |
| GET | `/v1/service-release/handoff/replay?directory=...` | Replay handoff verification |
| GET | `/v1/storage/audit` | Audit local object bytes, index pointers, reachability, and replay integrity |
| GET | `/v1/module-fabric/bundle` | Build the public 21-artifact module-fabric bundle projection |
| GET | `/v1/module-fabric/bundle/query` | Query bundle artifacts or public aggregate records |
| GET | `/v1/module-fabric/bundle/observability` | Return deterministic bundle events and metrics |
| GET | `/v1/module-fabric/bundle/runtime` | Run the staged bundle assembly and replay receipt |
| GET | `/v1/module-fabric/bundle/schema` | Return the closed bundle manifest schema |
| GET | `/v1/module-fabric/bundle/audit` | Reconcile module-fabric fixture, runtime, release, and projection artifacts |
| GET | `/v1/validation-design/bundle` | Build the public 27-artifact D13 validation-design bundle |
| GET | `/v1/validation-design/bundle/query` | Query validation-design artifacts, records, checks, or source receipts |
| GET | `/v1/validation-design/bundle/schema` | Return the closed validation-design bundle manifest schema |
| GET | `/v1/validation-design/bundle/audit` | Reconcile validation-design fixture, runtime, release, replay, and projections |
| GET | `/v1/validation-design/bundle/observability` | Return normalized D13 bundle stage counts and address health |
| GET | `/v1/validation-design/bundle/runtime` | Run the staged D13 bundle assembly, audit, observability, and replay gate |
| GET | `/v1/capability-certification/bundle` | Build the public 12-artifact capability certification bundle |
| GET | `/v1/capability-certification/bundle/query` | Query certified bundle certificates, domains, checks, or artifacts |
| GET | `/v1/capability-certification/bundle/observability` | Return certification bundle events and metrics |
| GET | `/v1/capability-certification/bundle/runtime` | Run bundle assembly and deterministic replay |
| GET | `/v1/capability-certification/bundle/schema` | Return the closed certification bundle schema |
| GET | `/v1/capability-certification/bundle/audit` | Reconcile all certification bundle artifacts and denominators |
| GET | `/v1/workbench-release/bundle` | Build the public 56-artifact D15 workbench-release handoff |
| GET | `/v1/workbench-release/bundle/query` | Query D15 artifacts, records, executions, checks, sources, stages, or indexes |
| GET | `/v1/workbench-release/bundle/observability` | Return normalized D15 49-stage observability |
| GET | `/v1/workbench-release/bundle/runtime` | Run D15 bundle assembly, audit, observability, and deterministic replay |
| GET | `/v1/workbench-release/bundle/schema` | Return the closed D15 offline manifest schema |
| GET | `/v1/workbench-release/bundle/audit` | Reconcile D15 fixture, runtime, release planes, and public projection |
| GET | `/v1/workbench-release/bundle/indexes` | Return address-only D15 artifact, record, operation, and stage indexes |
| GET | `/v1/workbench-release/bundle/boundary` | Audit D15 public keys and bundle boundary |
| GET | `/v1/workbench-release/bundle/reconciliation` | Return independent D15 denominator and address reconciliation |
| GET | `/v1/workbench-release/bundle/summary` | Return compact D15 operation and reviewer denominators |
| GET | `/v1/workbench-release/bundle/certification` | Return D15 technical certification domains and evidence references |
| GET | `/v1/workbench-release/bundle/closure-query` | Query independent D15 closure rows with bounded filters |
| GET | `/v1/workbench-release/bundle/closure-schema` | Return the D15 closure row schema and public policy |
| GET | `/v1/workbench-release/bundle/closure-boundary` | Audit D15 closure paths, addresses, and public keys |
| GET | `/v1/workbench-release/bundle/closure-indexes` | Return ten D15 closure lookup indexes and their audit |
| GET | `/v1/workbench-release/bundle/closure-reconciliation` | Return 44 independent D15 closure reconciliation checks |
| GET | `/v1/workbench-release/bundle/closure-summary` | Return operation, queue, issue, state, and runtime counters |
| GET | `/v1/workbench-release/bundle/closure-certification` | Return ten-domain, 60-check D15 closure certification |
| GET | `/v1/workbench-release/bundle/closure-observability` | Return 184 closure events and 24 closure metrics |
| GET | `/v1/workbench-release/bundle/closure-runtime` | Run the fourteen-stage D15 closure runtime |
| GET | `/v1/workbench-release/bundle/closure-failures` | Return twelve D15 negative-control results |
| GET | `/v1/workbench-release/bundle/closure-graph` | Return the connected D15 closure graph |
| GET | `/v1/workbench-release/bundle/closure-export` | Return the exact-byte D15 closure export manifest |
| GET | `/v1/deployment-frontier/bundle/closure-query` | Query 19 independent D16 closure resources with bounded filters |
| GET | `/v1/deployment-frontier/bundle/closure-schema` | Return D16 closure row schemas and aggregate-only policy |
| GET | `/v1/deployment-frontier/bundle/closure-boundary` | Audit D16 closure paths, addresses, and public keys |
| GET | `/v1/deployment-frontier/bundle/closure-indexes` | Return ten D16 closure lookup indexes and their audit |
| GET | `/v1/deployment-frontier/bundle/closure-reconciliation` | Return 47 independent D16 closure reconciliation checks |
| GET | `/v1/deployment-frontier/bundle/closure-summary` | Return D16 operation, state, issue, queue, and runtime counters |
| GET | `/v1/deployment-frontier/bundle/closure-certification` | Return ten-domain, 60-check D16 closure certification |
| GET | `/v1/deployment-frontier/bundle/closure-observability` | Return 151 D16 closure events and 24 aggregate metrics |
| GET | `/v1/deployment-frontier/bundle/closure-runtime` | Run the fourteen-stage D16 closure runtime and replay gate |
| GET | `/v1/deployment-frontier/bundle/closure-failures` | Return twelve D16 structural negative-control results |
| GET | `/v1/deployment-frontier/bundle/closure-graph` | Return the connected D16 closure graph |
| GET | `/v1/deployment-frontier/bundle/closure-export` | Return the exact-byte D16 closure export packet |
| GET | `/v1/frontier-release/closure` | Build the aggregate D13-D16 snapshot with four domains and 155 artifacts |
| GET | `/v1/frontier-release/closure/query` | Query aggregate domains, artifacts, dependencies, gates, or runtime rows |
| GET | `/v1/frontier-release/closure/schema` | Return the aggregate five-resource schema and public-key audit |
| GET | `/v1/frontier-release/closure/boundary` | Audit aggregate paths, identities, addresses, and forbidden keys |
| GET | `/v1/frontier-release/closure/indexes` | Return seven address-only aggregate lookup indexes and their audit |
| GET | `/v1/frontier-release/closure/reconciliation` | Return 35 aggregate denominator and dependency checks |
| GET | `/v1/frontier-release/closure/summary` | Return conserved source, artifact, gate, certification, and graph counters |
| GET | `/v1/frontier-release/closure/certification` | Return eight-plane, 48-check aggregate release certification |
| GET | `/v1/frontier-release/closure/observability` | Return 193 aggregate release events and 24 metrics |
| GET | `/v1/frontier-release/closure/graph` | Return the connected 189-node/191-edge aggregate release graph |
| GET | `/v1/frontier-release/closure/failures` | Return twelve aggregate structural negative-control results |
| GET | `/v1/frontier-release/closure/plan` | Return the 13-step dependency-ordered release plan |
| GET | `/v1/frontier-release/closure/runtime` | Run the 12-stage aggregate release runtime and replay gate |
| GET | `/v1/frontier-release/closure/export` | Return the 13-artifact exact-byte aggregate release packet |
| GET | `/v1/program-release/closure` | Build the top-level D01-D16 aggregate release snapshot |
| GET | `/v1/program-release/closure/query` | Query domains, artifacts, dependencies, gates, or runtime rows |
| GET | `/v1/program-release/closure/schema` | Return the D01-D16 schema and public-boundary audit |
| GET | `/v1/program-release/closure/boundary` | Audit aggregate paths, identities, addresses, and public keys |
| GET | `/v1/program-release/closure/indexes` | Return seven address-only indexes and their audit |
| GET | `/v1/program-release/closure/reconciliation` | Return nineteen source and aggregate denominator checks |
| GET | `/v1/program-release/closure/summary` | Return source and aggregate counters |
| GET | `/v1/program-release/closure/certification` | Return 96 domain certification checks |
| GET | `/v1/program-release/closure/observability` | Return 266 deterministic events and 96 metrics |
| GET | `/v1/program-release/closure/operations` | Return the sixteen-operation execution matrix and audit |
| GET | `/v1/program-release/closure/graph` | Return the connected 251-node aggregate graph |
| GET | `/v1/program-release/closure/failures` | Return twelve negative-control results |
| GET | `/v1/program-release/closure/plan` | Return the 23-step ordered release plan |
| GET | `/v1/program-release/closure/runtime` | Run the fourteen-stage closure runtime and replay gate |
| GET | `/v1/program-release/closure/export` | Return the fifteen-artifact exact-byte release packet |
| GET | `/v1/search` | Replay-gated cross-run search over public dossier resources |
| GET | `/v1/search/closure` | Complete content-addressed cross-run search closure |
| GET | `/v1/portfolio` | Reconcile run integrity, review operations, workspace state, and release readiness |
| GET | `/v1/portfolio/closure` | Complete cross-run portfolio closure for offline operations |
| GET | `/v1/portfolio/release` | Build a bounded, namespaced multi-run release package projection |
| GET | `/v1/portfolio/release/lineage` | Return the address-only release → member → artifact/check lineage graph |
| GET | `/v1/portfolio/release/observability` | Return deterministic package events and metrics |
| GET | `/v1/portfolio/release/schema` | Return the closed portfolio manifest schema |
| GET | `/v1/batches` | Paginated catalog of persisted batch evaluations |
| GET | `/v1/batches/{batch_id}` | Reopen and verify one batch result |
| GET | `/v1/batches/{batch_id}/release` | Build a gated portable batch handoff bundle |
| GET | `/v1/status` | Compact capability, program, operational, D01-D16, and boundary status |
| GET | `/v1/capabilities` | Certified capability query |
| GET | `/v1/architecture/program` | Architecture receipt query |
| GET | `/v1/architecture/operational` | Full stage, artifact, and check handoff trace |
| GET | `/v1/architecture/diff` | Baseline comparison with a named control |
| GET | `/v1/runs` | Paginated catalog of persisted case runs |
| GET | `/v1/runs/{run_id}` | Bounded summary and integrity status for one run |
| GET | `/v1/runs/{run_id}/dossier` | Reopen the immutable stored dossier |
| GET | `/v1/runs/{run_id}/events` | Reopen the hash-chained event record |
| GET | `/v1/runs/{run_id}/replay` | Return replay verification evidence |
| GET | `/v1/runs/{run_id}/inspection` | Return the complete run inspection closure |
| GET | `/v1/runs/{run_id}/workspace` | Reopen a replay-verified case as a bounded workspace projection |
| GET | `/v1/runs/{run_id}/review-workspace` | Reopen a replay-verified run as a provenance-first review workspace; optional `baseline_run_id` emits deltas |
| GET | `/v1/runs/{run_id}/review-workspace/query` | Filter and page public review collections with complete-match facets |
| GET | `/v1/runs/{run_id}/review-workspace/export` | Return deterministic JSON, Markdown, or one CSV review projection; use `format` and optional `collection` query parameters |
| GET | `/v1/runs/{run_id}/review-workspace/plan` | Build an ordered, dependency-checked descriptive triage plan |
| GET | `/v1/runs/{run_id}/review-workspace/plan/query` | Filter and page plan actions with complete-match facets |
| GET | `/v1/runs/{run_id}/review-workspace/plan/execution` | Replay the local review-plan execution ledger |
| GET | `/v1/runs/{run_id}/review-workspace/plan/execution/query` | Filter replayed execution actions with complete-match facets |
| GET | `/v1/runs/{run_id}/review-workspace/plan/execution/query?view=events` | Return the ordered replay-verified execution event timeline with sequence, filters, and facets |
| GET | `/v1/runs/{run_id}/workspace/closure` | Return the complete content-addressed run workspace closure |
| GET | `/v1/runs/{run_id}/workspace/history` | Rebuild every verified dossier snapshot as a workspace timeline |
| GET | `/v1/runs/{run_id}/workspace/compare` | Compare two historical workspace snapshots by public record identity |
| GET | `/v1/runs/{run_id}/workspace/release` | Build a gated portable workspace handoff bundle |
| GET | `/v1/runs/{run_id}/history` | List content-addressed dossier snapshots for one run |
| GET | `/v1/runs/{run_id}/compare/{target_run_id}` | Compare current or selected snapshots from two runs |
| GET | `/v1/runs/{run_id}/compare/{target_run_id}/release` | Build a gated portable comparison handoff bundle |
| GET | `/v1/runs/{run_id}/summary` | Aggregate evidence, review, and validation counters |
| GET | `/v1/runs/{run_id}/query-closure` | Complete content-addressed dossier query projection |
| GET | `/v1/runs/{run_id}/hypotheses` | Filter bounded hypothesis projections |
| GET | `/v1/runs/{run_id}/evidence` | Filter bounded evidence-claim projections |
| GET | `/v1/runs/{run_id}/experiments` | Filter bounded validation-route projections |
| GET | `/v1/runs/{run_id}/lineage` | Join hypothesis edges to referenced claims |
| GET | `/v1/runs/{run_id}/release` | Build a gated, content-addressed portable dossier release bundle |
| POST | `/v1/runs/{run_id}/review` | Attach a typed human review and create a new dossier snapshot |
| GET | `/v1/review-queue` | Return a bounded deterministic priority queue for review operations |
| GET | `/v1/review-queue/closure` | Return the complete review queue with state and priority counters |
| GET | `/v1/review-operations` | Return an as-of SLA, aging, and reviewer workload projection |
| GET | `/v1/review-operations/closure` | Return the complete SLA and workload closure |
| POST | `/v1/runs/{run_id}/assignment` | Append a durable reviewer assignment and create a new dossier snapshot |
| POST | `/v1/evaluate` | Existing case evaluation endpoint |
| POST | `/v1/evaluate-batch` | Evaluate a manifest list with independent item outcomes |

Capability queries accept `capability_id`, `domain_id`, `mvp_only`, `state`, and
`text`. Architecture queries accept `domain_id`, `accepted_only`, and `text`.
Boolean values accept `true`, `false`, `1`, `0`, `yes`, and `no`. Diff controls
are `none`, `missing-fixture`, and `missing-runtime`. Invalid query values return
HTTP 400 with the `invalid_query` error code.

Run catalog queries accept `case_id`, `status`, `text`, `offset`, and `limit`.
The limit is bounded to 100 rows. Run identifiers are validated before they are
used as filesystem paths. Missing runs return HTTP 404; an existing run can be
accepted only when its input object, event chain, dossier address, and stored
object links all verify.

Cross-run search accepts `q` or its `text` alias, `resource` (`all`, `runs`,
`hypotheses`, `evidence`, `experiments`, or `reviews`), `case_id`, `status`,
`reviewer`, `review_state`, `state`, `tier`, `channel`, `min_support`,
`max_uncertainty`, `assay`, `accepted_only`, `offset`, and `limit`. Search
reopens and verifies every persisted run before emitting scientific records.
Corrupt or incomplete runs contribute only a bounded blocked-run record for
`all` or `runs`; they never contribute hypotheses, claims, experiments, or
reviews. Results use deterministic token matching, ranking, pagination, and
content addresses. `/v1/search/closure` disables pagination and returns the
complete replay-gated projection for offline handoff.

The run portfolio joins each persisted run's replay integrity, review queue and
SLA state, current workspace history, and portable workspace release gate. It
accepts `case_id`, `status`, `reviewer`, `due_state`, `release_state`, `q` or
`text`, `release_ready_only`, `as_of`, `due_soon_hours`, `offset`, and `limit`.
Rows distinguish a valid inspectable run from a release-ready run: a pending
review can remain accepted as operational evidence while its release remains
blocked. `/v1/portfolio/closure` returns every row and aggregate status counts.

`/v1/portfolio/release` accepts the portfolio filters plus repeated or
comma-separated `run_id`, `max_runs`, `include_blocked`, and `include_payloads`.
It returns a content-addressed package projection with namespaced member
artifacts. Every member retains dossier and workspace release state; a blocked
member is inspectable but prevents package acceptance. Artifact bytes are
public-projected before publication, and the package contract rejects private
identifiers, attribution/language metadata, path traversal, duplicate paths,
missing artifacts, and address drift.

`/v1/portfolio/release/lineage` accepts the same selection filters and an
optional `focus_run_id`; the focused form returns that member and its
downstream artifacts. `/v1/portfolio/release/observability` emits stable
selection/member/check events plus byte, artifact, gate, and warning metrics.
`/v1/portfolio/release/schema` is read-only and does not inspect the data root.

The module-fabric bundle endpoints are read-only public aggregate projections.
`/v1/module-fabric/bundle` accepts optional `bundle_id`, `run_id`, and
`include_payloads` parameters. The query route accepts `resource` (`artifacts`
or `records`), `domain_id`, `capability_id`, `role`, `state`,
`artifact_kind`, `q` or `text`, `offset`, `limit`, and `include_payloads`.
The bundle is assembled deterministically from the checked-in 16-domain
fixture; the response includes its exact manifest address and 21-artifact
inventory. The observability, runtime, and schema routes do not expose raw
payloads unless explicitly requested through the public projection option.

The storage audit is read-only and store-wide. It checks canonical UTF-8 JSON,
filename content addresses, malformed object references, run and batch index
structure, replay reopening, missing pointers, unexpected filesystem entries,
and unreachable object files. It returns metadata and addresses only; it never
returns object payloads or repairs/deletes anything.

Batch catalog queries accept `text`, `offset`, and `limit`. Batch identifiers are
derived from the canonical batch input address, so repeating an identical batch
request reopens the existing result instead of creating a competing record.
Batch evaluation accepts an object with `manifests`, optional `batch_id` or
`label`, `live_reference`, `window_bp`, and `max_items`, or a bare JSON manifest
list in offline CLI use; a single case manifest is also accepted as a one-item
batch. Every item is evaluated independently. A failed item
retains its index, case identifier, input address, stable error category, and
error message beside successful run and dossier addresses. The batch is accepted
only when every requested item succeeds; partial results remain inspectable but
are never promoted as an accepted batch.

Dossier-plane queries accept `offset`, `limit`, and resource-specific filters.
Evidence supports `state`, `tier`, `channel`, `source_id`, `edge_id`, and
`evidence_id`; hypotheses support `hypothesis_id`, `status`, `min_support`, and
`max_uncertainty`; experiments support `option_id` and `assay`. The lineage
projection accepts `hypothesis_id` and fails closed when an edge references a
missing claim.

Review queue queries accept `scope` (`open`, `all`, `assigned`, `unassigned`,
`completed`, or `blocked`), `case_id`, `status`, `reviewer`, `queue_id`,
`priority_band`, `text`, `offset`, and `limit`. Queue priority is deterministic:
integrity blocks, returned or pending reviews, missing reviews, runtime warnings,
uncertainty, abstained evidence, and missing assignments contribute explicit
priority reasons. The queue remains a projection over replay-verified runs and
fails closed when any persisted run is corrupted.

Review operations accepts the same scope plus `reviewer`, `queue_id`,
`due_state`, `priority_band`, `text`, `offset`, `limit`, `as_of`, and
`due_soon_hours`. Due states are `completed`, `overdue`, `due_soon`,
`scheduled`, `undated`, and `invalid`. Every report includes the normalized UTC
clock, age in seconds, remaining seconds when a due time exists, an explicit
operational action, deterministic reviewer/queue workloads, and content
addresses. Supplying `as_of` is recommended for reproducible exports; omitting
it uses the current UTC instant for interactive use.

Run workspaces reopen the persisted manifest and current dossier only after the
run's input object, event chain, and dossier address pass replay verification.
The projection accepts `q` or `text`, `context_key`, repeated or
comma-separated `record_type`, `state`, `source_id`, and `tag` filters, plus
`chromosome`, `start`, `end`, `variant_id`, `offset`, and `limit`. It returns
the exact-context records, sections, facets, state, and variant relationships
used by the typed workspace builders. Direct subject/sample keys and agent,
model, author, attribution, and language metadata are removed before the
public content address is calculated. A failed run remains visible as a
blocked projection with integrity evidence; its workspace records are
withheld. The `/workspace/closure` route pages through every matching record
and marks the page complete for offline consumers.

Workspace history rebuilds every accepted dossier snapshot against the original
manifest, retains the snapshot and review-state metadata, and compares adjacent
public records by stable `record_id`. Each transition reports additions,
removals, field-level changes, unchanged records, truncation state, and review
metadata changes. The history route accepts `change_limit`; the compare route
requires `source_snapshot` and `target_snapshot` and accepts the same limit.
History fails closed when any indexed dossier snapshot or its run replay is
invalid, while retaining blocked snapshot warnings for inspection.

Workspace releases package the replay-gated history into eight portable public
artifacts: current and historical JSON projections, a summary, snapshot/record/
transition CSVs, gate evidence, and a Markdown report. `release.json` addresses
the exact artifact bytes and the verifier rejects missing, extra, unsafe,
duplicate, tampered, non-UTF-8, and public-boundary-violating files. A blocked
history or pending-review workspace can be exported for inspection, but its
release remains unaccepted until replay, workspace-boundary, and human-review
gates all pass.

## Service-release registry

The cached service snapshot now includes the D01-D16 program-release aggregate
and exposes it in the top-level status, service closure, and public-boundary
inventory. The separate service-release registry composes six accepted public
surfaces into a promotion-ready handoff with 13 exact-byte artifacts, 15
dependencies, 24 gates, 78 events, 24 metrics, five views, eight negative
controls, and a fourteen-stage replayable runtime. See
`docs/SERVICE_RELEASE_REGISTRY.md` for the full contract, query filters,
export paths, and verification checklist.

The service snapshot status includes:

| Field | Meaning |
| --- | --- |
| `program_release.snapshot_address` | D01-D16 aggregate content address |
| `program_release.domain_count` | Sixteen closed program domains |
| `program_release.artifact_count` | Eighteen portable source artifacts |
| `program_release.dependency_count` | One hundred twenty ordered dependencies |
| `program_release.gate_count` | Ninety-six D01-D16 gates |
| `program_release.domain_percent` | Accepted domain coverage |
| `program_release.gate_percent` | Passed gate coverage |

The registry is available through `/v1/service-release/*` and the
`service-release` CLI command. Its API query is bounded to surfaces, artifacts,
dependencies, and gates and returns a deterministic `has_more` pagination
indicator.

## CLI and offline closure

Run the compact status projection:

```text
glio-noncode service-surface --output service-status.json
```

Run the detailed archival projection:

```text
glio-noncode service-surface --closure --output service-surface-closure.json
```

Run the repository-wide public-boundary audit:

```text
glio-noncode public-surface-audit --output public-surface-audit.json
```

The audit covers 87 named projections across the service, capability
certification bundle, module-fabric bundle, schemas, service-release registry,
durable service-release handoff, authenticated deployment profile/schema,
versioned reference manifest/schema, and closures. Runtime
projections must contain no attribution, language, or direct-private-key
paths. The schema projection is the one deliberate exception: it may declare
subject/sample input field names because those names define an input contract,
but it may not publish values for those fields.

Evaluate and reopen a durable batch:

```text
glio-noncode evaluate-batch batch.json --data-root .glio --output batch-result.json
glio-noncode batch-inspect batch-<content-digest> --data-root .glio --output batch-inspection.json
glio-noncode batch-catalog --data-root .glio --output batch-catalog.json
glio-noncode batch-release batch-<content-digest> --data-root .glio --output batch-release
glio-noncode batch-release-verify batch-release --output batch-release-verification.json
```

Batch releases contain `release.json`, a private-key-filtered batch input
projection plus result JSON, summary and gate JSON, item/failure/run CSV
projections, and a Markdown report. The original input remains bound by its
content address in the gate evidence. Every artifact carries its byte count,
line count, and byte content address.
`batch-release-verify` reopens the directory, rejects unsafe or duplicate paths,
detects byte and manifest-address tampering, and preserves blocked partial
bundles as inspectable evidence.

Search the persisted corpus across runs:

```text
glio-noncode run-search --data-root .glio --query enhancer --resource hypotheses --output search.json
glio-noncode run-search --data-root .glio --resource evidence --state supported --closure --output evidence-search-closure.json
glio-noncode run-portfolio --data-root .glio --as-of 2026-09-01T12:00:00Z --output run-portfolio.json
glio-noncode run-portfolio --data-root .glio --closure --as-of 2026-09-01T12:00:00Z --output run-portfolio-closure.json
glio-noncode storage-audit --data-root .glio --output storage-audit.json
```

The search command is the offline equivalent of the two search endpoints. It
keeps the public dossier boundary, records scanned and blocked run counts, and
returns an explicit `accepted` flag so filtered results cannot conceal a
corrupted persisted run.

Inspect persisted case work:

```text
glio-noncode run-catalog --data-root .glio
glio-noncode run-catalog --data-root .glio --closure --output run-catalog-closure.json
glio-noncode run-inspect run-<run-id> --data-root .glio --output run-inspection.json
glio-noncode run-workspace run-<run-id> --data-root .glio --record-type evidence --state supported --output run-workspace.json
glio-noncode run-workspace run-<run-id> --data-root .glio --variant-id variant-1 --closure --output run-workspace-closure.json
glio-noncode run-workspace-history run-<run-id> --data-root .glio --output run-workspace-history.json
glio-noncode run-workspace-compare run-<run-id> 0 1 --data-root .glio --output workspace-transition.json
glio-noncode run-workspace-release run-<run-id> --data-root .glio --output workspace-release
glio-noncode run-workspace-release-verify workspace-release --output workspace-release-verification.json
glio-noncode run-review run-<run-id> review.json --data-root .glio --output reviewed-dossier.json
glio-noncode run-query run-<run-id> summary --data-root .glio --output run-summary.json
glio-noncode run-query run-<run-id> lineage --data-root .glio --output run-lineage.json
glio-noncode run-query run-<run-id> closure --data-root .glio --output dossier-query-closure.json
glio-noncode run-history run-<run-id> --data-root .glio --output run-history.json
glio-noncode run-compare run-<source-id> run-<target-id> --data-root .glio --output run-comparison.json
glio-noncode run-compare run-<run-id> run-<run-id> --source-snapshot 0 --target-snapshot 1 --data-root .glio --output review-transition.json
glio-noncode run-compare-release run-<run-id> run-<run-id> --source-snapshot 0 --target-snapshot 1 --data-root .glio --output comparison-release
glio-noncode run-compare-release-verify comparison-release --output comparison-verification.json
glio-noncode run-release run-<run-id> --data-root .glio --output dossier-release
glio-noncode run-release-verify dossier-release --output release-verification.json
glio-noncode review-queue --data-root .glio --scope open --output review-queue.json
glio-noncode review-queue --data-root .glio --closure --output review-queue-closure.json
glio-noncode review-operations --data-root .glio --as-of 2026-09-01T12:00:00Z --output review-operations.json
glio-noncode review-operations --data-root .glio --closure --as-of 2026-09-01T12:00:00Z --output review-operations-closure.json
glio-noncode review-assign run-<run-id> assignment.json --data-root .glio --output assignment-result.json
```

Review input uses the public `ReviewDecision` fields: `review_id`, `case_id`,
`reviewer`, `state`, `reviewed_hypothesis_ids`, `rationale`, and
`checked_claim_ids`. Accepted reviews produce a new `released_research` dossier
snapshot while retaining the research-use-only policy boundary and prior
content-addressed objects.

Review continuation is append-only: when a persisted run is reopened, the
existing verified event record is hydrated before the new `review_recorded`
event is appended. If the chain is invalid, the review is rejected rather than
silently replacing the history with a new chain.

Every persisted run now retains an ordered `dossier_history` of immutable
snapshot addresses. `run-history` verifies each snapshot independently and
reports the current index, review state, counts, and any missing or mismatched
object. `run-compare` and the compare route can select historical indexes and
return semantic additions, removals, and field-level changes for metadata,
hypotheses, evidence, and experiments. Comparisons require replay integrity,
matching case identity, a complete bounded projection, and the public boundary;
failed checks remain visible in the returned evidence.

Comparison handoffs are portable ten-artifact bundles containing canonical JSON,
summary/check JSON, Markdown, source and target history closures, and separate
metadata, hypothesis, evidence, and experiment CSV deltas. The release route and
`run-compare-release` command retain blocked comparisons as inspectable bundles;
`run-compare-release-verify` reopens the directory and verifies every byte,
manifest address, size, line count, and safe artifact path.

Review assignments are append-only `review_assigned` events. An assignment
records the public assignment identifier, reviewer, queue, optional due time and
note, and its content address. The runtime re-addresses the dossier with the
new event head, so assignment history is retained in `run-history`, semantic
comparisons, and subsequent release gates. Reassignments use a new assignment
identifier and never overwrite prior events.

The release route and CLI export ten portable artifacts: canonical dossier JSON,
Markdown, summary and query-closure JSON, replay events, release-gate evidence,
review JSON, and evidence/hypothesis/experiment CSV projections. Release is
accepted only when replay integrity, accepted human review, structural policy,
byte addressing, and the public boundary all pass. Filesystem bundles can be
reopened with `run-release-verify`; tampering, unsafe paths, missing files, and
manifest-address changes are reported as verification failures.

The closure includes the complete 256-row capability certification report, the
sixteen-domain architecture runtime, the twelve-stage operational trace, and
the common query projections. The closure is rejected if its public projection
contains a private-key field.

The capability-certification bundle surface is available at:

- `GET /v1/capability-certification/bundle`
- `GET /v1/capability-certification/bundle/query?resource=certificates&domain_id=D05`
- `GET /v1/capability-certification/bundle/observability`
- `GET /v1/capability-certification/bundle/runtime`
- `GET /v1/capability-certification/bundle/schema`
- `GET /v1/capability-certification/bundle/audit`

The bundle endpoints expose the same addressed twelve-artifact public handoff
as the CLI, including 256 certificates, 16 domains, 2,572 checks, bounded
offline query filters, deterministic replay, and the closed public boundary.

The D14 evidence-lifecycle offline bundle surface is available at:

- `GET /v1/evidence-lifecycle/bundle`
- `GET /v1/evidence-lifecycle/bundle/query?resource=records&operation=graph_construction`
- `GET /v1/evidence-lifecycle/bundle/observability`
- `GET /v1/evidence-lifecycle/bundle/runtime`
- `GET /v1/evidence-lifecycle/bundle/schema`
- `GET /v1/evidence-lifecycle/bundle/audit`
- `GET /v1/evidence-lifecycle/bundle/indexes`
- `GET /v1/evidence-lifecycle/bundle/boundary`
- `GET /v1/evidence-lifecycle/bundle/reconciliation`
- `GET /v1/evidence-lifecycle/bundle/summary`

These endpoints expose the same 21-artifact handoff as the CLI, with bounded
queries over artifacts, records, checks, sources, and events. The runtime and
audit routes retain deterministic replay and independent cross-artifact
reconciliation.

The D15 workbench-release offline bundle surface is available at:

- `GET /v1/workbench-release/bundle`
- `GET /v1/workbench-release/bundle/query?resource=records&operation=review_form`
- `GET /v1/workbench-release/bundle/observability`
- `GET /v1/workbench-release/bundle/runtime`
- `GET /v1/workbench-release/bundle/schema`
- `GET /v1/workbench-release/bundle/audit`
- `GET /v1/workbench-release/bundle/indexes`
- `GET /v1/workbench-release/bundle/boundary`
- `GET /v1/workbench-release/bundle/reconciliation`
- `GET /v1/workbench-release/bundle/summary`
- `GET /v1/workbench-release/bundle/certification`

These routes expose the same 56-artifact handoff as the CLI. The query route
supports bounded filters over artifacts, records, executions, evaluation checks,
sources, normalized stages, operation partitions, denominator indexes, and the
public-key inventory. The route remains read-only and research-scoped.
The certification route adds seven named technical domains and a coverage
receipt over the bundle audit without making a clinical or causal claim.
## Whole-product release assurance

The service also exposes a read-only aggregate gate at
`/v1/release-assurance`. It composes the accepted capability, architecture,
service-release, and repository public-boundary projections without returning
their source records. The gate has four domains, 20 evidence links, 28 checks,
12 runtime stages, 48 events, 16 metrics, 20 plan steps, four views, eight
negative controls, and ten exact-byte export artifacts.

```text
GET /v1/release-assurance
GET /v1/release-assurance/status
GET /v1/release-assurance/query?resource=checks&passed_only=true
GET /v1/release-assurance/schema
GET /v1/release-assurance/indexes
GET /v1/release-assurance/summary
GET /v1/release-assurance/observability
GET /v1/release-assurance/graph
GET /v1/release-assurance/failures
GET /v1/release-assurance/plan
GET /v1/release-assurance/views
GET /v1/release-assurance/runtime
GET /v1/release-assurance/export
GET /v1/release-assurance/handoff
GET /v1/release-assurance/handoff/status?directory=...
GET /v1/release-assurance/handoff/inspect?directory=...
GET /v1/release-assurance/handoff/verify?directory=...
GET /v1/release-assurance/handoff/query?directory=...&role=runtime
GET /v1/release-assurance/handoff/diff?left_directory=...&right_directory=...
GET /v1/release-assurance/handoff/replay?directory=...
```

The CLI mirrors these projections with `release-assurance --plane snapshot`,
`status`, `query`, `schema`, `indexes`, `summary`, `observability`, `graph`,
`failures`, `plan`, `views`, `runtime`, and `export`. An export directory can
be checked with `release-assurance-export-verify`. The full contract is in
[RELEASE_ASSURANCE.md](RELEASE_ASSURANCE.md).
