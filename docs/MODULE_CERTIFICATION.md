# Module certification and contract coverage

## Purpose

The module certification control plane turns the repository-wide static module
inventory into a module-by-module contract matrix. It answers a narrower and
more useful question than a raw line count: for every source module, which
parts of its implementation contract are evidenced, which parts are missing,
and what work should happen next?

The implementation is deliberately static. It does not import discovered
modules, call discovered functions, inspect runtime globals, or require a
private dataset. Source bytes are inspected through the existing AST inventory;
test and Markdown evidence is tokenized once per file; package exposure is
inspected from the package initializer AST.

## Matrix model

There is one `ModuleCertificationRow` for every `ModuleRecord` in the input
inventory. Rows are sorted by their package-qualified `module_id` and contain:

| Field | Meaning |
| --- | --- |
| `module_id` | Stable package-qualified module identifier |
| `family` | Inventory family classification |
| `role` | Core, domain, frontier, integration, or support role |
| `physical_lines` | Static physical-line count from inventory |
| `public_symbol_count` | Public class/function symbol count from inventory |
| `checks` | Eight ordered check results |
| `passed_count` | Number of passing checks |
| `failed_count` | Number of failed checks |
| `not_applicable_count` | Internal-surface checks that do not apply |
| `score` | `passed / (passed + failed)`; N/A is excluded |
| `state` | Certified, review, blocked, or uncovered |
| `gap_count` | Number of failed checks and remediation gaps |
| `content_address` | Deterministic row address |

The matrix also conserves the module count, check count, state counts, and gap
count. Its aggregate score is the arithmetic mean of module scores. The
aggregate is a repository engineering signal, not a scientific or clinical
claim.

## Check planes

Every module receives these checks in the same order:

1. `parse` — inventory state is `parsed`.
2. `symbol` — a public symbol surface exists, or the check is N/A for an
   internal module.
3. `dependency` — local dependency edges are resolved, or no local imports
   exist.
4. `test` — test text contains the module identifier or inventory has a test
   reference. Public modules without evidence fail this check; internal modules
   are N/A.
5. `documentation` — Markdown evidence contains the module identifier or its
   source filename. Public modules without evidence fail; internal modules are
   N/A.
6. `export` — the package initializer statically exposes the module, or the
   module is an initializer. Public modules without evidence fail; internal
   modules are N/A.
7. `boundary` — the module identifier contains no forbidden identity or
   attribution token.
8. `scale` — the module is within the static 1–100,000 physical-line review
   bound. An empty file is N/A.

Each failed check produces a gap with the same check kind and module ID. Gap
priority is deterministic: parse and boundary are highest, dependency follows,
then tests, documentation, exports, symbol surface, and scale. Integration
documentation and export gaps are promoted because integration boundaries need
explicit review.

## States and thresholds

The row state rules are:

- `blocked` if parse, dependency, or boundary fails;
- `certified` if no check fails and the score is at least 0.80;
- `review` if at least one applicable check exists but the row is not certified;
- `uncovered` if no applicable checks exist.

The default aggregate policy requires an overall score of 0.80, at least 80%
certified modules, zero blocked modules, and permits up to 10,000 review
modules. It also requires tests for domain modules, documentation for
integration modules, and exports for public modules. The default gate will
therefore remain blocked while the repository is being instrumented; this is an
intentional release signal, not an attempt to hide the remaining work.

Policies are immutable typed objects. Thresholds, role requirements, N/A
handling, and the policy address are included in the gate. A gate is accepted
only when every independent check passes:

| Gate check | Rule |
| --- | --- |
| Input acceptance | Matrix and remediation plan are accepted |
| Minimum overall score | Matrix score meets policy |
| Minimum certified percent | Certified share meets policy |
| Blocked limit | Blocked count is within policy |
| Review limit | Review count is within policy |
| Domain test coverage | Required domain test checks do not fail |
| Integration documentation | Required integration documentation checks do not fail |
| Public export coverage | Required export checks do not fail |
| N/A policy | N/A checks are allowed or absent |
| Failed-check closure | Failed checks equal gaps |
| Task-gap closure | Every task reference points to a known gap |

## Remediation and review

`ModuleCertificationTaskPlan` creates exactly one task for each failed check.
Task kinds are `repair_parse`, `repair_dependency`, `add_test_coverage`,
`add_documentation`, `review_export`, `review_boundary`, and `review_module`.
Tasks carry the source gap ID, sorted evidence tokens, deterministic priority,
and a concise next action. No task execution is performed by this control
plane; the plan is a read-only work queue.

`ModuleCertificationReviewQueue` groups gaps by module for human routing. Its
severity rules are:

- blocking: parse, dependency, or boundary gaps;
- high: integration documentation or export gaps;
- medium: ordinary test, documentation, or export gaps;
- low: symbol and scale review gaps.

The queue conserves every gap and retains the check-kind list so grouping never
loses the underlying evidence.

## Runtime stages

The timestamp-free runtime has seven ordered stages:

| Order | Stage | Output |
| ---: | --- | --- |
| 1 | inventory | Typed inventory selection |
| 2 | evidence | Static evidence inputs |
| 3 | checks | Eight checks per module |
| 4 | gaps | Ordered failed-check queue |
| 5 | tasks | Remediation task plan |
| 6 | policy | Aggregate gate checks |
| 7 | public | Public aggregate boundary result |

The runtime address depends only on the typed inputs and deterministic stage
outputs. It contains no wall-clock time, absolute path, machine username, or
execution identity.

## Observability

Observability exposes six stable events—inventory, checks, gaps, tasks, policy,
and runtime—and aggregate metrics for module counts, check counts, state counts,
score, gaps, tasks, policy checks, and stage count. Events are bounded to 256;
queries are bounded to 512 rows. CSV and JSON projections use a trailing newline
for text artifacts and preserve deterministic ordering.

## Matrix diffs

`build_module_certification_diff` compares two matrices by module ID. It records
added, removed, changed, and unchanged rows, plus score deltas, physical-line
deltas, public-symbol deltas, gap deltas, and changed check kinds. A source
edit that does not change a certification-visible field remains unchanged by
design; the input matrix address still changes and can be used to correlate the
source inventory diff.

## Offline packet

The packet is a fixed ten-artifact directory plus `manifest.json`:

| Artifact | Format | Purpose |
| --- | --- | --- |
| `matrix.json` | JSON | Full matrix rows and gaps |
| `checks.csv` | CSV | Flat check evidence table |
| `gaps.csv` | CSV | Flat remediation gap queue |
| `tasks.json` | JSON | Ordered typed task plan |
| `tasks.csv` | CSV | Flat task table |
| `gate.json` | JSON | Policy and gate checks |
| `audit.json` | JSON | Independent closure audit |
| `runtime.json` | JSON | Seven-stage runtime receipt |
| `observability.json` | JSON | Events and metrics |
| `summary.json` | JSON | Compact aggregate summary |

Every artifact has a byte count, line count, media type, relative safe path,
and exact UTF-8 content address. The writer uses a temporary file followed by
an atomic replacement for each file and refuses an existing destination unless
`--allow-existing` is supplied.

Verification checks manifest readability, artifact count, path safety, exact
byte and line counts, exact byte addresses, and the public boundary. A verified
packet can be loaded and queried without reopening the source tree. Packet
queries support artifacts, checks, matrix, modules, gaps, tasks, and summary;
packet diffs compare artifact addresses; replay returns a compact resource
closure receipt.

## CLI

```powershell
glio-noncode module-certification --format summary
glio-noncode module-certification --resource gaps --limit 100
glio-noncode module-certification-tasks --format csv --output certification-tasks.csv
glio-noncode module-certification-audit --output certification-audit.json
glio-noncode module-certification-runtime --output certification-runtime.json
glio-noncode module-certification-observability --format events-csv --output events.csv
glio-noncode module-certification-packet --destination certification-packet
glio-noncode module-certification-packet-verify certification-packet
glio-noncode module-certification-packet-query certification-packet --resource modules --limit 25
```

Schema and capability commands exist for the base matrix, policy, tasks,
runtime, audit, observability, packet, packet query, diff, review, and schema
report contracts.

## HTTP API

All certification routes are GET-only and use the existing deployment profile
authorization and bounded response behavior. The primary routes are:

```text
/v1/module-certification
/v1/module-certification/query
/v1/module-certification/schema
/v1/module-certification/capabilities
/v1/module-certification/audit
/v1/module-certification/policy
/v1/module-certification/tasks
/v1/module-certification/runtime
/v1/module-certification/observability
/v1/module-certification/packet
/v1/module-certification/packet/verify?directory=...
/v1/module-certification/packet/query?directory=...&resource=gaps
/v1/module-certification/packet/diff?left_directory=...&right_directory=...
/v1/module-certification/packet/replay?directory=...
```

Each route returns a public aggregate projection. Source payloads, absolute
paths, and machine-local metadata are not part of the public schema.

## Actions checks

Continuous integration compiles the package, runs the focused certification
test module, and materializes the certification schema and capability
projections. The full unit suite remains the final compatibility check. A
failed aggregate gate is reportable output; it does not prevent developers from
running the matrix or inspecting the remediation queue.

## Limitations

Static evidence is intentionally conservative. A token in a test or document
does not prove semantic coverage. Package initializer inspection does not
resolve dynamic exports. Unresolved imports may be false positives around
optional dependencies. The scale bound identifies a review need; it does not
prove poor design. These limitations are retained in the evidence and should be
addressed with focused implementation work and tests, not silently converted
into acceptance.
