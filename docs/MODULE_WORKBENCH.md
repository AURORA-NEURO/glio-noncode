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

## Scale and determinism

The workbench keeps the expensive source traversal in the upstream inventory
and lineage layers. Workbench aggregation itself uses indexed module IDs,
reverse dependency sets, grouped evidence rows, and one pass over each typed
assessment. Task generation is bounded to one row per task kind per module, so
queue size grows linearly with the module count rather than with the number of
possible remediation combinations. Family rollups use grouped counters and
are emitted in sorted order.

Every projection is deterministic under the same upstream bytes and options:

- module, task, family, policy, audit, runtime, and portfolio rows have stable
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

All list and query routes enforce bounded pagination. JSON projections are
timestamp-free and addressable. A failed aggregate gate returns an
unprocessable response while still returning the complete explanatory check
body.

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
