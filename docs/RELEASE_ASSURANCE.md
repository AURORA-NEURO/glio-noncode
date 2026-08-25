# Whole-product release assurance

Release assurance is the final public readiness gate for GLIO-NONCODE. It
joins already-addressed subsystem contracts without copying their source
records. The result is a small, deterministic, addressable projection that
answers one operational question:

> Do the certified capability, architecture, service-release, and public
> boundary surfaces agree that this checkout can be published?

The gate is a release projection, not a scientific interpretation. It does not
change dossier evidence, infer variant effects, or promote a research
hypothesis to a clinical decision.

## Four assurance planes

Every snapshot contains exactly four domain rows. Each row retains a source
content address, a denominator, an accepted count, a readiness percentage,
five evidence links, and five domain checks.

| Plane | Source | Denominator | Acceptance signal |
| --- | --- | ---: | --- |
| `capability-catalog` | capability certification | 256 capability rows | accepted certifications |
| `architecture-program` | D01–D16 program release | 16 architecture domains | accepted domain receipts |
| `service-release` | public service registry | 6 service surfaces | accepted registry surfaces |
| `public-surface` | repository public-surface audit | 47 audited surfaces | passed public projections |

The row denominator is conserved from the source plane. Readiness is the
accepted count divided by the denominator, rounded to two decimal places. The
overall percentage is the arithmetic mean of the four row percentages. A
100.0% percentage is informative but is not sufficient by itself: every
check, source, export boundary, and replay stage must also pass.

## Snapshot contract

The snapshot has four domains, twenty evidence links, and twenty-eight checks.
Each domain receives five evidence roles:

1. `primary-source` points to the source plane address.
2. `summary` points to the source summary projection.
3. `boundary` points to the public-boundary audit.
4. `replay` records the deterministic runtime input.
5. `release` points to the aggregate release decision.

The twenty domain checks cover source addresses, denominator conservation,
accepted partitions, evidence coverage, and readiness calculation. Eight
cross-plane checks cover domain closure, source agreement, D01 program
registration, the 47-surface audit, accepted totals, service acceptance, and
recursive public-boundary safety.

All rows and checks use content addresses. Queries return address-only public
projections. The snapshot does not retain case manifests, patient fields,
private source payloads, free-form attribution, model metadata, or language
metadata.

## Runtime stages

`run_release_assurance` executes twelve ordered stages. Each stage records its
ordinal, identifier, input address, output address, state, and detail.

| Stage | Identifier | Purpose |
| ---: | --- | --- |
| 1 | `source-surface` | reuse or build the service snapshot |
| 2 | `public-audit` | reuse or build the public-surface audit |
| 3 | `assurance-snapshot` | assemble the four planes |
| 4 | `cross-plane-checks` | reconcile all 28 checks |
| 5 | `indexes` | build address-only indexes |
| 6 | `summary` | conserve readiness counters |
| 7 | `observability` | publish deterministic events and metrics |
| 8 | `graph` | connect source, evidence, and checks |
| 9 | `negative-controls` | run fail-closed mutation probes |
| 10 | `plan-and-views` | prepare execution steps and reviewer views |
| 11 | `replay` | rebuild the snapshot twice |
| 12 | `public-state` | publish the final release state |

The runtime is accepted only when all source planes, every check, all indexes,
summaries, events, graph nodes, negative controls, plan steps, views, and the
two replay addresses are accepted. A failed stage is `blocked` and remains
visible in the report; it is never silently omitted.

## Query surface

The bounded query function supports `domains`, `checks`, and `evidence`.
Results are sorted by domain and stable row identifier, then paginated with an
offset and limit. Supported filters are:

- `domain_id` for one of the four assurance planes;
- `plane` for the check plane;
- `state` for a state value;
- `passed_only` for accepted or passed rows; and
- `text` for deterministic case-insensitive row matching.

The query result retains the bundle identifier, filters, total row count,
offset, limit, bounded items, `has_more`, acceptance, and a content address.
CSV and Markdown renderers use the same filtered rows and the same public
boundary policy.

## API endpoints

The local service exposes the aggregate gate under `/v1/release-assurance`.
Every endpoint is read-only and emits JSON.

| Endpoint | Output |
| --- | --- |
| `/v1/release-assurance` | addressed four-plane snapshot |
| `/v1/release-assurance/status` | compact readiness counters |
| `/v1/release-assurance/reconciliation` | independent conservation rows and audit |
| `/v1/release-assurance/diff` | address-only comparison with another bundle/run |
| `/v1/release-assurance/catalog` | ten-entry public resource catalog |
| `/v1/release-assurance/compliance` | metadata, address, and path compliance |
| `/v1/release-assurance/performance` | structural cardinality budgets |
| `/v1/release-assurance/operations` | deterministic operator queue |
| `/v1/release-assurance/report` | reviewer Markdown report and runtime |
| `/v1/release-assurance/checkpoint` | portable checkpoint over deep projections |
| `/v1/release-assurance/review` | deterministic reviewer queue |
| `/v1/release-assurance/history` | append-only runtime and review history |
| `/v1/release-assurance/thresholds` | explicit fail-closed readiness thresholds |
| `/v1/release-assurance/query` | bounded domains, checks, or evidence page |
| `/v1/release-assurance/schema` | schema and validation checks |
| `/v1/release-assurance/indexes` | address-only indexes and audit |
| `/v1/release-assurance/summary` | conserved summary and audit |
| `/v1/release-assurance/observability` | 48 events and 16 metrics |
| `/v1/release-assurance/graph` | connected lineage graph |
| `/v1/release-assurance/failures` | eight negative-control results |
| `/v1/release-assurance/plan` | twenty executable plan steps |
| `/v1/release-assurance/views` | four reviewer tables |
| `/v1/release-assurance/runtime` | twelve-stage runtime report |
| `/v1/release-assurance/export` | ten-artifact export packet |

The snapshot and runtime accept `bundle_id` and `run_id` query parameters.
Query accepts `resource`, `domain_id`, `assurance_plane`, `state`,
`passed_only`, `text` or `q`, `offset`, and `limit`. Invalid resources,
duplicate parameters, invalid booleans, and out-of-contract pagination return
bounded client errors.

## CLI commands

The CLI mirrors the API so the same contracts can run in offline Actions jobs:

```text
glio-noncode release-assurance --plane snapshot --output release-assurance.json
glio-noncode release-assurance --plane status --output release-status.json
glio-noncode release-assurance --plane query --resource checks --passed-only
glio-noncode release-assurance --plane reconciliation --output release-reconciliation.json
glio-noncode release-assurance --plane catalog --output release-catalog.json
glio-noncode release-assurance --plane compliance --output release-compliance.json
glio-noncode release-assurance --plane performance --output release-performance.json
glio-noncode release-assurance --plane operations --output release-operations.json
glio-noncode release-assurance --plane report --format markdown --output release-report.md
glio-noncode release-assurance --plane checkpoint --output release-checkpoint.json
glio-noncode release-assurance --plane review --output release-review.json
glio-noncode release-assurance --plane history --format markdown --output release-history.md
glio-noncode release-assurance --plane thresholds --output release-thresholds.json
glio-noncode release-assurance --plane schema --output release-schema.json
glio-noncode release-assurance --plane runtime --output release-runtime.json
glio-noncode release-assurance --plane export --destination release-assurance-export
glio-noncode release-assurance-export-verify release-assurance-export
```

The command exits zero only for an accepted projection. The export verifier
also checks the manifest, exact byte counts, content addresses, safe relative
paths, missing files, unexpected files, duplicate entries, tampering, and
public-boundary violations.

## Observability, graph, and plan

The observability projection has twelve event types for each of the four
domains, for 48 ordered events. It also publishes four metrics per domain:
denominator, accepted count, readiness percentage, and evidence count. Event
and metric identifiers are deterministic and addressable.

The graph has 53 nodes and 52 edges: one aggregate root, four domain nodes,
twenty evidence nodes, and twenty-eight check nodes. Domain checks are linked
from their domain node; cross-plane checks are linked from the aggregate root.
The graph audit validates node coverage, edge references, and root
connectivity.

The portable checkpoint joins six deep projections: runtime, reconciliation,
catalog, compliance, performance, and operations. It retains only their
content addresses and acceptance states. The append-only history then records
runtime stages, checkpoint components, and reviewer items as a sequence of
addressed events. History supports bounded event-type, state, and text
filters, CSV, Markdown, and an independent sequence/address audit.

The plan has ten phases and two ordered steps per phase. The phases are source,
capability, architecture, service, boundary, evidence, checks, summary,
runtime, and release. Every step carries at least one check identifier and a
source or prior-step address.

The four reviewer views are:

- `readiness-matrix`, one row per plane;
- `check-matrix`, one row per check;
- `evidence-matrix`, one row per evidence link; and
- `release-status`, one aggregate row.

## Negative controls

The failure-injection report contains eight controls. Each mutation is
expected to fail closed, and the expected failure category is itself checked:

| Control | Mutation |
| --- | --- |
| `missing-domain` | remove one domain row |
| `failed-check` | flip a check to failed |
| `missing-evidence` | remove one evidence link |
| `duplicate-evidence` | duplicate an evidence identifier |
| `blank-source` | erase the source address |
| `unsafe-path` | attempt parent traversal in an export path |
| `forbidden-key` | inject prohibited public metadata |
| `replay-drift` | alter a replay input |

These controls are structural checks. They do not claim scientific validity;
they ensure that broken release projections remain visible and blocked.

## Exact-byte export

The export packet contains ten artifacts:

1. `runtime/release-assurance.json`
2. `runtime/status.json`
3. `assurance/summary.json`
4. `assurance/domains.csv`
5. `assurance/checks.csv`
6. `assurance/evidence.csv`
7. `assurance/observability.json`
8. `assurance/plan.json`
9. `assurance/views.json`
10. `assurance/schema.json`

Each artifact includes a safe relative path, media type, byte count, line
count, content address, and exact bytes. `manifest.json` records the packet
denominator and the artifact records. JSON artifacts are canonicalized with a
terminal newline. CSV artifacts have sorted columns and a terminal newline.

## Durable handoff

`release-assurance-handoff` is the durable filesystem boundary above the
in-memory runtime and the ten-artifact export. It packages nineteen aggregate
artifacts and a public manifest so another machine can verify the release
without rebuilding the capability, architecture, or service source planes.

The handoff includes:

1. `assurance/snapshot.json`
2. `runtime/release-assurance.json`
3. `runtime/status.json`
4. `assurance/summary.json`
5. `assurance/reconciliation.json`
6. `assurance/catalog.json`
7. `assurance/compliance.json`
8. `assurance/performance.json`
9. `assurance/operations.json`
10. `assurance/checkpoint.json`
11. `assurance/review.json`
12. `assurance/history.json`
13. `assurance/thresholds.json`
14. `assurance/observability.json`
15. `assurance/plan.json`
16. `assurance/views.json`
17. `assurance/schema.json`
18. `reports/release-assurance.md`
19. `reports/history.csv`

The manifest records the bundle and run identifiers, artifact and required
artifact denominators, source addresses, media types, safe paths, byte counts,
line counts, exact-byte content addresses, roles, and acceptance. Artifact
content is not embedded in the manifest. The manifest address is recomputed
from its canonical public fields during verification.

Build a new handoff with:

```text
glio-noncode release-assurance-handoff --plane build --destination release-assurance-handoff
glio-noncode release-assurance-handoff --plane status --directory release-assurance-handoff
glio-noncode release-assurance-handoff --plane inspect --directory release-assurance-handoff
glio-noncode release-assurance-handoff --plane verify --directory release-assurance-handoff
glio-noncode release-assurance-handoff --plane query --directory release-assurance-handoff --role runtime
glio-noncode release-assurance-handoff --plane replay --directory release-assurance-handoff
glio-noncode release-assurance-handoff-verify release-assurance-handoff
```

The handoff writer uses atomic sibling temporary files and refuses to write
into a non-empty directory unless `--allow-existing` is explicitly supplied.
It never recursively deletes an existing handoff. The verifier rejects missing
files, unexpected files, duplicate artifact identifiers, duplicate paths,
unsafe relative paths, symlinks, byte-count drift, line-count drift, content
address drift, malformed JSON, boundary violations, stale manifest versions,
and manifest denominator drift.

Manifest inspection is intentionally cheaper than full verification and is
useful for catalog tooling. A query always performs verification before
returning artifact rows, so a failed or tampered directory remains visibly
blocked. Query filters include resource, artifact identifier, role, media type,
required-only, text, offset, and limit. The status projection returns the
handoff state, acceptance, checked count, missing count, unexpected count,
tampered count, and verification address.

Two handoffs can be compared without opening their source projections:

```text
glio-noncode release-assurance-handoff --plane diff --directory release-assurance-handoff --right-directory release-assurance-handoff-next
```

The diff reports added, removed, changed, and unchanged artifact identifiers.
It compares content addresses rather than paths or timestamps. Verification
replay runs the full directory verifier twice and returns both verification
addresses; a replay is accepted only when both are accepted and identical.

The local API exposes the same boundary below
`/v1/release-assurance/handoff`:

| Endpoint | Output |
| --- | --- |
| `/v1/release-assurance/handoff` | build an in-memory handoff metadata packet |
| `/v1/release-assurance/handoff/status` | verify and return compact status |
| `/v1/release-assurance/handoff/inspect` | inspect manifest metadata |
| `/v1/release-assurance/handoff/verify` | return detailed filesystem verification |
| `/v1/release-assurance/handoff/query` | query verified manifest artifacts |
| `/v1/release-assurance/handoff/diff` | compare two handoff directories |
| `/v1/release-assurance/handoff/replay` | replay verification twice |

The API build route returns packet metadata and exact artifact metadata, not
filesystem bytes. Filesystem routes require an explicit local directory
parameter and preserve all verification failures in their JSON response.

## Public-boundary policy

The release-assurance support layer recursively converts values to JSON-safe
projections and rejects prohibited keys or private-key tokens before export.
It also rejects absolute paths, parent traversal, drive-qualified paths, and
unsafe path components. The same policy is applied to snapshots, queries,
schema artifacts, observability, views, and on-disk verification.

The aggregate boundary is intentionally narrow. It carries readiness,
addresses, counts, checks, and release operations. Source records remain in
their own governed subsystem and are referenced only by content address.

## Threshold semantics

Threshold evaluation is deliberately separate from the percentage summary.
The summary describes what was observed; thresholds decide whether the
observed state is sufficient for a release handoff. This separation prevents a
large denominator from hiding one failed plane or one failed runtime stage.

The base threshold set requires:

- overall readiness of at least 100.0%;
- every domain readiness value of at least 100.0%;
- zero failed checks;
- an accepted snapshot; and
- both upstream source addresses.

When a runtime is supplied, three additional thresholds apply:

- the runtime itself must be accepted;
- every one of the twelve stage states must be `ready`; and
- replay must be deterministic and accepted.

Each threshold has a stable identifier, expected value, observed value,
pass/fail state, detail, and content address. Threshold identifiers are
unique, results are addressable, and the report is accepted only when every
result passes. A blocked threshold is returned to clients rather than being
converted to a warning or omitted from the report.

The threshold API is intentionally cheap when called without a runtime. This
supports health checks that need only the cached snapshot. CI and offline
handoffs should call the runtime command and threshold projection together so
that stage and replay gates are included. The CLI returns a non-zero status for
any failed threshold, which makes the projection suitable for a required
Actions job.

## History semantics

The append-only history is a reviewer projection, not a replacement for the
runtime event log. It starts at the snapshot address, records each runtime
stage in order, then records the six checkpoint components, and finally
records the reviewer queue items. Every event has one input and one output
address. The next event consumes the previous event's output address, making
the chain inspectable without exposing source payloads.

History filters never reorder events. An event-type filter can isolate runtime
stages, checkpoint components, or review items; a state filter can isolate
ready or blocked events; and text matching is deterministic over the public
event fields. CSV and Markdown exports preserve the sequence order and use
the same boundary checks as the JSON projections.

A history audit verifies bundle and run linkage, non-empty event closure,
contiguous sequence numbers, unique event identifiers, input/output address
presence, acceptance propagation, and reproducible history addressing. This
gives reviewers a compact audit trail while keeping the full runtime report
available for detailed investigation.

Threshold and history reports are safe to persist in public build artifacts.
They contain no case content, no private source values, and no runtime
attribution fields. Their addresses can be compared across builds, and their
failed identifiers can be routed to the review queue without reconstructing a
case dossier.

For an accepted handoff, retain the snapshot address, runtime address,
checkpoint address, threshold address, and history address together. This
five-address set is enough to locate every aggregate projection. It is also
small enough to include in a release note or an offline verification manifest.
When any address changes, rerun the reconciliation, compliance, performance,
operations, review, history, and threshold audits before publishing the new
handoff.

The verifier should preserve the original byte artifacts beside these
addresses for later audit.

This keeps the final handoff reproducible.

It is deterministic.
It is bounded.
It is public-safe.
It is replayable.
It is reviewable.
It is addressable.
It is fail-closed.
It is offline-capable.
It is CI-verifiable.
It is source-preserving.

## Verification contract

The focused suite in `tests/test_release_assurance.py` covers:

- all four domain and cross-plane denominators;
- schema, status, summary, and query reconciliation;
- index, graph, observability, and negative-control audits;
- plan and reviewer view closure;
- twelve-stage runtime replay;
- exact-byte export round trips and tamper detection;
- HTTP routes and invalid-resource behavior; and
- CLI snapshot and schema commands.

The GitHub Actions workflow runs the focused suite, runtime command, schema
command, and repository public-surface audit alongside the existing subsystem
checks. A release is ready for review only when those jobs and the checked-in
public service closure remain accepted.

## Extension rules

New aggregate evidence must first exist as an accepted source projection. Add
its source address to a domain evidence link, add a bounded check, update the
denominator constants, update the schema, add a negative control when the
failure mode is new, and add a focused test. Do not place source records or
free-form metadata in this layer.

If a new plane is required, add it to the domain identifier tuple and update
the plan, observability, graph, index, view, export, and schema denominators in
one build. The release gate must remain deterministic and replayable after the
change.
