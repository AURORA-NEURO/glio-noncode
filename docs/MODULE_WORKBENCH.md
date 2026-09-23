# Module implementation workbench

The module implementation workbench is the repository's detailed planning
surface for deep, module-by-module development. It combines the static module
inventory, certification matrix, evidence lineage, and quality report into one
deterministic report. The result describes each source module, measures the
dimensions that make implementation durable, classifies delivery risk, and
emits a bounded next-action queue.

The workbench is intentionally read-only. It does not import discovered source
modules, execute discovered functions, modify source files, or require a
private dataset. It records package-qualified module IDs, relative paths only
through upstream digests, counts, classifications, and content addresses.

## Build chain

The workbench consumes four typed upstream objects:

1. `ModuleInventory` — parsed modules, symbols, imports, local dependencies,
   test references, and source content addresses.
2. `ModuleCertificationMatrix` — per-module parse, symbol, dependency, test,
   documentation, export, boundary, and scale checks.
3. `ModuleCertificationLineage` — source, test, documentation, export, and
   dependency evidence links.
4. `ModuleCertificationQualityReport` — aggregate coverage, family measures,
   blocker modules, and readiness state.

All four upstream addresses are conserved in `ModuleWorkbenchReport`. A
workbench cannot be built from mismatched inventory, matrix, lineage, or
quality objects. This prevents a report from combining module rows from one
snapshot with evidence from another.

## Per-module assessment

There is one `ModuleWorkbenchAssessment` for every inventory module. Rows are
sorted by `module_id`. Each row contains structural counters and an explainable
set of seven dimensions:

| Dimension | Signal | Default target |
| --- | --- | ---: |
| `connectivity` | resolved fan-in plus fan-out | 6 links |
| `dependency_resolution` | resolved local imports divided by imports | all imports |
| `evidence` | linked lineage artifacts | 3 artifacts |
| `implementation_scale` | nonblank source lines | 240 lines |
| `parse` | accepted static parse state | parsed |
| `public_contract` | public class/function symbols | 5 symbols |
| `test_references` | static test references | 2 references |

Each dimension stores its name, normalized score, observed count, target
count, detail, and content address. The module score is the arithmetic mean of
these seven normalized signals. The score is a repository engineering signal;
it is not a scientific, clinical, or correctness claim.

The assessment also records:

- physical and nonblank source lines;
- public symbols, classes, functions, and imports;
- resolved local dependency count;
- fan-in and fan-out from the resolved module graph;
- test-reference and lineage-evidence counts;
- sorted evidence kinds;
- sorted blockers and strengths;
- the upstream module content address.

## Depth bands

The workbench classifies the aggregate score after applying hard blockers:

| Band | Rule |
| --- | --- |
| `blocked` | parse, local dependency, certification, or quality blocker exists |
| `starter` | score is below 0.35 with no hard blocker |
| `established` | score is at least 0.35 and below 0.62 |
| `deep` | score is at least 0.62 and below 0.84 |
| `comprehensive` | score is at least 0.84 |

`depth_percent` is the percentage of modules in the `deep` or
`comprehensive` bands. The report separately conserves exact `deep_count`,
`comprehensive_count`, `starter_count`, and `blocked_count` values.

## Risk classification

Risk is independent from depth. This makes a large, well-covered integration
module visible even when its depth score is strong:

| Risk | Rule |
| --- | --- |
| `blocker` | at least one hard blocker exists |
| `high` | score is below 0.55 or static parsing is not accepted |
| `medium` | score is below 0.76, fan-out exceeds 16, or source exceeds 900 nonblank lines |
| `low` | none of the above applies |

The report conserves all four risk counts and exposes `high_risk_count` as the
sum of blocker and high-risk modules. Fan-in highlights modules whose contract
changes affect many callers; fan-out highlights modules whose implementation
depends on many local surfaces.

## Action queue

The workbench emits at most one task of each kind per module. Every task has a
stable ID of the form `module_id:task_kind`, a bounded priority from 0 to 100,
a title, rationale, acceptance statement, estimated impact, evidence addresses,
and its own content address. Tasks are sorted by stable ID in the conserved
report; operator views sort them by priority first.

The task kinds are:

| Kind | Emitted when | Intended outcome |
| --- | --- | --- |
| `repair_parse` | static parsing fails | recover symbols and dependency evidence |
| `resolve_dependency` | a package-local import is unresolved | close the local graph or declare an external edge |
| `add_test` | fewer than two test references exist | add focused executable behavior coverage |
| `add_documentation` | no documentation evidence is linked | document inputs, outputs, failure behavior, and boundaries |
| `expand_public_contract` | fewer than five public symbols exist | clarify intended exports without incidental helpers |
| `decompose_oversized` | more than 900 nonblank lines exist | separate cohesive responsibilities and reduce change concentration |
| `review_integration` | fan-in is at least 8 or fan-out is at least 16 | add compatibility notes and impact coverage |
| `close_certification` | certification is not `certified` | close failed checks with linked static evidence |

Tasks are descriptive planning records. They do not automatically change the
repository. This separation lets a reviewer inspect the proposed work before
implementation and compare queues across snapshots.

## Family rollups

`ModuleWorkbenchFamilyRollup` conserves one row per inventory family. It
includes module count, deep and comprehensive counts, blocked and high-risk
counts, average score, average test references, average evidence, average
fan-out, and the three most frequent task kinds. Family rows are sorted and
content addressed.

## CLI

Build the complete report:

```text
glio-noncode module-workbench --format json --output module-workbench.json
```

Use a compact summary for dashboards:

```text
glio-noncode module-workbench --format summary --output module-workbench-summary.json
```

Render the operator view or export a resource:

```text
glio-noncode module-workbench --format markdown --output module-workbench.md
glio-noncode module-workbench --resource tasks --format csv --output module-tasks.csv
glio-noncode module-workbench --resource families --format csv --output module-families.csv
```

Run bounded queries:

```text
glio-noncode module-workbench --resource modules --risk high --limit 50
glio-noncode module-workbench --resource modules --depth-band blocked
glio-noncode module-workbench --resource tasks --kind add_test --limit 100
glio-noncode module-workbench --resource modules --module-id glio_noncode.module_inventory
```

The complete report command can consume the same durable cache after the
observability build, avoiding a second source parse in scripts or Actions:

```text
glio-noncode module-workbench --format summary \
  --cache-root .glio/module-cache --output module-workbench-summary.json
```

The same cache-root contract is available on the detail, policy, audit,
runtime, portfolio, triage, and execution control-plane commands. They reuse
the addressed inventory, certification, lineage, quality, and workbench
artifacts before producing their own projections, so a script can walk the
full review surface without rebuilding the source chain for every command:

```text
glio-noncode module-workbench-detail --module-id glio_noncode.module_inventory \
  --cache-root .glio/module-cache --output module-detail.json
glio-noncode module-workbench-policy --format summary \
  --cache-root .glio/module-cache --output module-policy.json
glio-noncode module-workbench-triage --format summary \
  --cache-root .glio/module-cache --output module-triage.json
glio-noncode module-workbench-execution --format summary \
  --cache-root .glio/module-cache --output module-execution.json
```

Execution audit, policy, runtime, review, packet, and packet-runtime exports
accept the same option. Diff commands preserve two independently rooted
snapshots and accept independent cache directories for each side:

```text
glio-noncode module-workbench-diff \
  --left-cache-root .glio/baseline-cache \
  --right-cache-root .glio/candidate-cache \
  --format json --output module-diff.json
glio-noncode module-workbench-execution-diff \
  --left-cache-root .glio/baseline-cache \
  --right-cache-root .glio/candidate-cache \
  --format json --output execution-diff.json
```

The two cache roots are never merged: each snapshot is validated against its
own source, test, and documentation signature before it contributes to the
comparison.

Build a complete dossier for one module, including its workbench assessment,
certification checks and gaps, lineage evidence, and planned tasks:

```text
glio-noncode module-workbench-detail --module-id glio_noncode.module_inventory --output module-detail.json
glio-noncode module-workbench-detail-schema
glio-noncode module-workbench-detail-capabilities
```

Emit the same timestamp-free, addressed observation used by the service. A
direct CLI invocation is a new process, so it truthfully reports `full` and
`cache_hit: false`; it never implies that a durable server snapshot was reused:

```text
glio-noncode module-workbench-observability --output module-workbench-observability.json
glio-noncode module-workbench-observability-schema
glio-noncode module-workbench-observability-capabilities
```

For repeated local or Actions runs, provide a cache directory. The first run
persists the exact gzip snapshot, unchanged inputs return `snapshot`, and a
source, test, or documentation change returns `incremental` while reusing only
unchanged source rows:

```text
glio-noncode module-workbench-observability \
  --cache-root .glio/module-cache \
  --output module-workbench-observability.json
```

The public Actions workflow runs this same sequence on Python 3.12 and uploads
both timestamp-free observations as the `module-workbench-cache-observations`
artifact. The job checks that the restart snapshot conserves the inventory and
workbench addresses and reports zero reparsed modules.

Cache-backed CLI commands also take a bounded cross-process lock beside the
snapshot. The default wait bound is 15 minutes, which accommodates a cold
build of a large repository on a slower Actions runner without leaving a
failed worker waiting forever. Concurrent workers therefore share one cold
build: the first worker hydrates or rebuilds the addressed chain, while later
workers reopen the exact snapshot after the lock is released. The lock file
contains no report data, is crash-released by the operating system, and is
rejected when its parent is symlinked.

## Portable report archives

The complete aggregate workbench can be handed to another reviewer as a
deterministic two-member ZIP archive. It contains only a canonical manifest
and the path-free `workbench.json` report; it never copies source, test,
documentation, downloaded data, absolute paths, timestamps, or private
identity fields. The archive can therefore be reloaded and queried on a
machine that does not have the analyzed repository:

```text
glio-noncode module-workbench-archive \
  --cache-root .glio/module-cache \
  --destination workbench.zip \
  --format markdown --output workbench-archive.md
glio-noncode module-workbench-archive-verify workbench.zip
glio-noncode module-workbench-archive-query workbench.zip \
  --resource modules --risk high --limit 50
glio-noncode module-workbench-archive-load workbench.zip \
  --output restored-workbench.json
```

Verification checks ZIP readability, duplicate and traversal-free member
names, regular-file metadata, canonical JSON, exact member bytes, typed report
hydration, every nested content address, state conservation, and the public
aggregate boundary. A valid archive preserves the original workbench address;
its report can be queried without rebuilding source inventory or accepting any
archive-contained executable content.

## Browser workbench

The local review workbench exposes the same module contract in the left rail
under `Modules`. It loads bounded pages from
`/v1/module-workbench/query?resource=modules`, then opens a selected module
through `/v1/module-workbench/detail?module_id=...`. A dossier shows the
implementation score and depth band, certification checks, evidence receipts,
lineage edges, planned tasks, and limitations. The browser only renders the
path-free public projection: source text, absolute paths, raw payloads, and
machine-specific metadata are not displayed.

The module list is generation-gated like the research archives, so a delayed
catalog response cannot replace a newer selection. Each selected dossier is
also checked for `module-workbench-detail-v1` and an accepted public boundary
before its detail panels are shown.

The sidebar also exposes the explainable priority queue from
`/v1/module-workbench/triage/query`. It provides bounded pagination and risk or
reason filters for `blocker_risk`, `high_risk`, `shallow_depth`,
`certification_gap`, `unresolved_lineage`, `high_fan_in`,
`missing_test_reference`, and `low_score`. Selecting a queue row opens the same
module dossier and preserves its rank, priority score, reason codes, dependency
pressure, evidence and gap counts, unresolved edges, and recommended task IDs
in the review-pressure panel. Queue responses are generation-gated and are
accepted only when the triage address, page bounds, and read-only contract are
valid.

The overview also loads `/v1/module-workbench/observability`. Its cache and
source-reuse panel distinguishes an exact durable `snapshot` from an
`incremental` or `full` rebuild, shows reused and reparsed module counts, and
shows source/test input counts. The panel validates that those counts conserve
the current module summary before displaying them; it does not display local
cache paths or source-root machine paths.

Each dossier also requests the bounded
`/v1/module-workbench/execution/query?resource=items&module_id=...` projection.
The execution panel shows selected task state, completion percentage, required
evidence coverage, prerequisite count, and ledger detail. A module with no
selected rows is explicitly reported as outside the current portfolio rather
than being treated as completed.

The API keeps the ranked triage object in a server-local cache keyed by the
same source signature as the module workbench. Repeated filter and pagination
requests reuse the verified report; any Python source or test-input change
invalidates the triage projection together with its upstream workbench chain.

Contract metadata is available without scanning source:

```text
glio-noncode module-workbench-schema
glio-noncode module-workbench-capabilities
```

## Policy gate

The workbench policy is a separate immutable contract. It can require a
minimum overall score and deep-module percentage, cap blocked and high-risk
counts, require a minimum family score, require a registered dimension set,
and set minimum test-reference and evidence counts. The balanced repository
default is deliberately explicit:

- minimum overall score: `0.70`;
- minimum deep or comprehensive percentage: `70.0`;
- maximum blocked modules: `0`;
- maximum high-risk modules: `500`;
- minimum family score: `0.45`;
- all seven workbench dimensions registered;
- at least one lineage artifact per module.

Evaluate the default gate:

```text
glio-noncode module-workbench-policy --format summary
glio-noncode module-workbench-policy --format markdown --output workbench-policy.md
glio-noncode module-workbench-policy --format csv --output workbench-policy.csv
```

The policy gate has independent checks for accepted inputs, blocked count,
depth percentage, dimension registry, evidence count, family score, high-risk
count, test references, and overall score. It fails closed when any check
fails.

## Independent audit

The audit recomputes workbench invariants from the typed report. It verifies:

- aggregate address presence;
- nested dimension, assessment, task, family, and report addresses;
- reserved-key boundary safety;
- depth-band conservation;
- family count conservation and order;
- module order and uniqueness;
- risk count conservation;
- task coverage, known-module references, uniqueness, and bounded priorities.

Run it with:

```text
glio-noncode module-workbench-audit
glio-noncode module-workbench-audit --format csv --output workbench-audit.csv
glio-noncode module-workbench-audit --plane tasks --passed
```

The audit is independent of the policy decision. A report may be structurally
valid while failing a deliberately strict policy threshold; both facts remain
visible.

## Complete runtime

`run_module_workbench` executes the seven-stage static chain and returns one
addressed `ModuleWorkbenchRuntime`. The stages are inventory, certification,
lineage, quality, workbench, policy, and audit. Each stage retains its typed
artifact address, accepted state, and a concise count-based detail. A failed
policy gate therefore remains visible without discarding the valid structural
artifacts that led to the decision.

```text
glio-noncode module-workbench-runtime --format json --output workbench-runtime.json
glio-noncode module-workbench-runtime --format csv --output workbench-stages.csv
glio-noncode module-workbench-runtime --resource stages --state blocked
glio-noncode module-workbench-runtime-schema
glio-noncode module-workbench-runtime-capabilities
```

The runtime is source-execution-free, timestamp-free, and path-free. It is
the preferred CI handoff when a caller needs the complete evaluation chain;
the individual report, policy, audit, and diff surfaces remain available for
focused review.

## Durable server cache

The HTTP server writes a compressed snapshot of the verified inventory,
certification matrix, lineage graph, quality report, and workbench report under
the configured data root at `module-cache/snapshot.json.gz`. The snapshot is
written atomically and carries a deterministic payload digest. A normal server
load checks that digest, the source metadata signature, typed structure, and
upstream relationships; the explicit snapshot verifier additionally recomputes
every nested content address.
Missing, stale, malformed, or tampered snapshots are ignored and rebuilt from
source; the server never executes cached source content. This keeps a cold
server restart useful for large repositories while preserving the same
fail-closed public boundary as an in-memory build.

## Bounded implementation portfolios

The task queue can be reduced to a concrete implementation wave with
`build_module_workbench_portfolio`. Selection accepts a total task capacity,
per-module cap, priority window, and optional risk filter. Candidates are
ranked by ascending priority, descending estimated impact, and stable task ID;
the persisted selection is sorted by task ID for reproducibility. The
portfolio reports selected module and family counts, deferred-task count, and
average estimated impact.

```text
glio-noncode module-workbench-portfolio --capacity 100 --max-tasks-per-module 2
glio-noncode module-workbench-portfolio --risk blocker --risk high --capacity 40
glio-noncode module-workbench-portfolio --minimum-priority 0 --maximum-priority 25 --format summary
glio-noncode module-workbench-portfolio-schema
glio-noncode module-workbench-portfolio-capabilities
```

This selection is a planning projection. It does not mutate source or mark a
task complete; after a build wave, the snapshot diff and the next portfolio
selection show exactly what changed and what remains deferred.

## Explainable module triage

`build_module_workbench_triage` ranks every module by review pressure. The
priority score combines risk, implementation depth, certification gaps,
unresolved lineage, fan-in, missing test references, score deficit, and task
pressure. Each row retains reason codes and up to three recommended task IDs,
so a rank is inspectable rather than a hidden heuristic.

```text
glio-noncode module-workbench-triage --format summary
glio-noncode module-workbench-triage --risk blocker --limit 25
glio-noncode module-workbench-triage --reason unresolved_lineage --format markdown
glio-noncode module-workbench-triage-schema
glio-noncode module-workbench-triage-capabilities
```

Triage is read-only and addressable. It conserves the workbench, certification
matrix, lineage, and quality addresses, sorts ties by stable module ID, and
supports bounded queries by module, risk, depth band, reason code, or text.

## Scale and determinism

The workbench keeps the expensive source traversal in the upstream inventory
and lineage layers. Workbench aggregation itself uses indexed module IDs,
reverse dependency sets, grouped evidence rows, and one pass over each typed
assessment. Task generation is bounded to one row per task kind per module, so
queue size grows linearly with the module count rather than with the number of
possible remediation combinations. Family rollups use grouped counters and
are emitted in sorted order.

Every projection is deterministic under the same upstream bytes and options:

- module, task, family, policy, audit, runtime, portfolio, and triage rows have stable
  ordering;
- content addresses hash canonical public fields and omit their own address;
- query pages preserve the selected resource order and include the query
  parameters in their own address;
- Markdown and CSV headers are fixed and timestamp-free;
- no random identifiers or wall-clock values are used;
- pagination has an explicit maximum of 512 rows per request.

This design supports repeatable Actions checks, offline review, and direct
comparison of two source snapshots. A new source digest naturally propagates
through inventory, certification, lineage, workbench, policy, audit, runtime,
and portfolio addresses, making stale handoffs detectable.

## Snapshot diff

The diff compares two workbench reports produced from two source roots. It
classifies every module as `added`, `changed`, `removed`, or `unchanged`, and
conserves score and task-count deltas. It never includes source payloads or
machine-local absolute paths.

```text
glio-noncode module-workbench-diff \
  --left-source-root baseline/src/glio_noncode \
  --right-source-root candidate/src/glio_noncode \
  --left-test-root baseline/tests \
  --right-test-root candidate/tests \
  --left-docs-root baseline/docs \
  --right-docs-root candidate/docs \
  --format csv --output workbench-diff.csv
```

The query surface supports `--kind`, `--module-id`, `--text`, `--offset`, and
`--limit`. Signed aggregate score and task deltas make improvement and
regression direction explicit.

## HTTP service

The API mirrors the CLI under `/v1/module-workbench`:

| Route | Function |
| --- | --- |
| `GET /v1/module-workbench` | complete report, summary, Markdown, or CSV projection |
| `GET /v1/module-workbench/query` | bounded module, task, family, risk, or summary query |
| `GET /v1/module-workbench/schema` | report schema |
| `GET /v1/module-workbench/capabilities` | report operations and guarantees |
| `GET /v1/module-workbench/detail?module_id=...` | one-module assessment, certification, lineage, and task dossier |
| `GET /v1/module-workbench/detail/schema` | one-module dossier schema |
| `GET /v1/module-workbench/detail/capabilities` | one-module dossier operations |
| `GET /v1/module-workbench/policy` | default policy gate or projection |
| `GET /v1/module-workbench/policy/query` | bounded policy check query |
| `GET /v1/module-workbench/policy/schema` | policy schema |
| `GET /v1/module-workbench/policy/capabilities` | policy operations |
| `GET /v1/module-workbench/audit` | independent invariant audit |
| `GET /v1/module-workbench/audit/query` | bounded audit check query |
| `GET /v1/module-workbench/audit/schema` | audit schema |
| `GET /v1/module-workbench/audit/capabilities` | audit operations |
| `GET /v1/module-workbench/diff/schema` | diff schema |
| `GET /v1/module-workbench/diff/capabilities` | diff operations |
| `GET /v1/module-workbench/triage` | ranked module review queue or projection |
| `GET /v1/module-workbench/triage/query` | bounded triage query by pressure signals |
| `GET /v1/module-workbench/triage/schema` | triage schema and reason codes |
| `GET /v1/module-workbench/triage/capabilities` | triage operations and guarantees |
| `GET /v1/module-workbench/archive` | portable report archive descriptor or projection |
| `GET /v1/module-workbench/archive/query` | bounded query over the current archive projection |
| `GET /v1/module-workbench/archive.zip` | exact-byte deterministic workbench download |
| `GET /v1/module-workbench/archive/schema` | archive member and boundary contract |
| `GET /v1/module-workbench/archive/capabilities` | archive operations and guarantees |

All list and query routes enforce bounded pagination. JSON projections are
timestamp-free and addressable. A failed aggregate gate returns an
unprocessable response while still returning the complete explanatory check
body. The server keeps one derived lineage, quality, and workbench snapshot
per source fingerprint, so adjacent module-workbench routes reuse the same
typed chain instead of rebuilding it independently. Any Python source or test
file metadata change invalidates that chain before the next request; CLI
invocations still build a fresh chain and expose that fact through the
observability command. The CLI becomes restart-aware when `--cache-root` is
provided; its cache uses the same canonical snapshot envelope as the service.

## Public boundary

The workbench schema and capabilities are part of the public-surface inventory.
The independent public-surface audit rejects reserved identity and attribution
keys recursively. The workbench has no public fields for private identity,
model metadata, language metadata, absolute paths, or timestamps. Content
addresses are derived from canonical public projections, so the same inputs
produce the same report bytes.

## Verification expectations

Focused tests cover root-package relative import resolution, typed report
conservation, bounded queries, CSV and Markdown projections, policy gates,
independent audits, and same-snapshot diffs. The Actions workflow runs these
focused tests in addition to compile and repository-wide test gates and checks
all workbench schema and capability commands.
