# Frontier release closure operations

## Purpose

The frontier release closure is the aggregate handoff for the four fresh
frontier domains D13, D14, D15, and D16. Each domain already has an independent
offline handoff with its own data, runtime, certification, and export
contracts. This layer composes those handoffs into one deterministic public
release package.

The aggregate package is deliberately address-oriented. It carries domain
identities, source artifact identities, dependency identities, gate results,
runtime receipts, and content addresses. It does not flatten source payloads
into a new scientific claim and it does not convert a release decision into a
clinical or biological conclusion.

## Boundary

The public boundary is:

```text
public_aggregate_frontier_release_closure_handoff
```

The current contract versions are:

| Contract | Version |
| --- | --- |
| Aggregate closure | `frontier-release-closure-v1` |
| Runtime | `frontier-release-runtime-v1` |
| Certification | `frontier-release-certification-v1` |
| Schema | `frontier-release-schema-v1` |
| Export | `frontier-release-export-v1` |

Only public aggregate projections are emitted. The boundary enforces:

1. four known domains in D13, D14, D15, D16 order;
2. domain-qualified artifact references;
3. safe relative export paths;
4. unique domain, artifact, dependency, and gate identities;
5. content addresses for every public receipt;
6. six forward-only dependencies;
7. six passing release gates per domain;
8. exact denominator conservation across all source handoffs;
9. deterministic replay of the complete snapshot;
10. recursive terminal-key checks over every public projection.

The terminal-key denylist is applied to generated public dictionaries before
acceptance. Input schemas and source data remain separate from this public
aggregate release boundary.

## Source composition

The aggregate builder runs the four source closure runtimes with one shared
run identifier. It then projects each source closure into a stable domain
record and names each source artifact with a domain prefix.

| Domain | Source bundle | Artifacts | Source receipts | Records | Evaluation checks | Closure stages |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| D13 | validation-design | 27 | 5 | 16 | 80 | 13 |
| D14 | evidence-lifecycle | 21 | 5 | 16 | 80 | 13 |
| D15 | workbench-release | 56 | 5 | 16 | 80 | 13 |
| D16 | deployment-frontier | 51 | 5 | 16 | 120 | 13 |
| Total | four source closures | 155 | 20 | 64 | 360 | 52 |

The source artifact denominator is calculated from the source closure manifests,
not from filenames in the repository. An aggregate artifact reference has the
form:

```text
D15:<source-artifact-id>
```

The aggregate artifact content address covers the domain, source address,
relative path, source bundle, and source artifact identity. A source artifact
change therefore changes both its projection address and the aggregate
snapshot address.

## Aggregate resource catalog

The query surface exposes five bounded resources. Every row is a dictionary
with a stable identity and a content address.

| Resource | Identity | Count | Primary use |
| --- | --- | ---: | --- |
| `domains` | `domain_id` | 4 | Source closure acceptance and provenance |
| `artifacts` | `artifact_ref` | 155 | Export and manifest inventory |
| `dependencies` | `dependency_id` | 6 | Release ordering and join validation |
| `gates` | `gate_id` | 24 | Domain-level release admission |
| `runtime` | `domain_id` | 4 | Source runtime depth and replay receipts |

Aliases are accepted for singular resource names and hyphenated names. Query
results are bounded to a default limit of 50 and a maximum limit of 500. The
result includes the bundle identifier, normalized filters, total matches,
offset, limit, rows, and a content address.

Supported filters are:

| Filter | Applies to | Behavior |
| --- | --- | --- |
| `domain_id` | all resources | Match one or more source domains |
| `gate_type` | gates | Match one or more gate families |
| `state` | domains, gates, runtime | Match accepted, passed, or blocked state |
| `relation` | dependencies | Match dependency relation |
| `accepted` | domains, runtime | Match accepted or blocked rows |
| `text` | all resources | Case-insensitive canonical row search |
| `offset` / `limit` | all resources | Apply bounded pagination |

## Dependency order

The release dependency matrix is intentionally small and forward-only:

| Dependency | Source | Target | Relation |
| --- | --- | --- | --- |
| `D13-to-D14` | D13 | D14 | `release_precedes` |
| `D13-to-D15` | D13 | D15 | `release_precedes` |
| `D13-to-D16` | D13 | D16 | `release_precedes` |
| `D14-to-D15` | D14 | D15 | `release_precedes` |
| `D14-to-D16` | D14 | D16 | `release_precedes` |
| `D15-to-D16` | D15 | D16 | `release_precedes` |

The dependency set is not a workflow engine. It is a release ordering receipt
that makes the composition graph inspectable and rejects cycles, duplicate
edges, reversed edges, and unknown endpoints.

## Release gates

Each domain receives six gates. The aggregate release contains 24 gate rows.

| Gate type | Required condition |
| --- | --- |
| `bundle_accepted` | The source closure root is accepted |
| `artifact_manifest` | The expected source artifact denominator is conserved |
| `certification_coverage` | The source certification is complete and accepted |
| `reconciliation` | The source reconciliation is accepted |
| `deterministic_replay` | The source replay addresses agree |
| `runtime_depth` | The source runtime has the required stage depth |

Gate rows include the domain identifier, expected and observed values, source
reference, and a content address. A gate failure changes the snapshot state to
blocked and prevents certification and export acceptance.

## Ordered release plan

The plan is a separately addressed 13-step receipt. Each step has an ordinal,
domain or aggregate scope, action, prerequisite IDs, input address, output
address, acceptance state, and content address.

| Ordinal | Step | Scope | Action |
| ---: | --- | --- | --- |
| 1 | `source-d13` | D13 | Materialize validation-design closure |
| 2 | `source-d14` | D14 | Materialize evidence-lifecycle closure |
| 3 | `source-d15` | D15 | Materialize workbench-release closure |
| 4 | `source-d16` | D16 | Materialize deployment-frontier closure |
| 5 | `aggregate-domains` | release | Aggregate four domain receipts |
| 6 | `index-artifacts` | release | Build namespaced artifact indexes |
| 7 | `order-dependencies` | release | Build the forward dependency matrix |
| 8 | `evaluate-gates` | release | Evaluate six gates per domain |
| 9 | `reconcile-release` | release | Reconcile cross-domain denominators |
| 10 | `certify-release` | release | Issue eight-plane certification |
| 11 | `observe-release` | release | Emit events and metrics |
| 12 | `graph-release` | release | Connect domains, artifacts, gates, and dependencies |
| 13 | `publish-release` | release | Finalize the exact-byte export packet |

The plan is accepted only if every prerequisite is present, every output is
addressed, all ordinals are contiguous, and all 13 steps are ready.

## Runtime

The runtime is a 12-stage state machine. Stage output addresses chain to the
next stage input address.

| Ordinal | Stage | Admission evidence |
| ---: | --- | --- |
| 1 | `snapshot` | Four-domain snapshot accepted |
| 2 | `domains` | Domain conservation |
| 3 | `artifacts` | Namespaced artifact conservation |
| 4 | `dependencies` | Forward dependency conservation |
| 5 | `gates` | All 24 gates pass |
| 6 | `boundary` | Public keys, paths, identities, and addresses pass |
| 7 | `indexes` | Seven lookup indexes materialize |
| 8 | `index_audit` | Index rows conserve source rows |
| 9 | `reconciliation` | 35 aggregate checks pass |
| 10 | `summary` | Summary and 20 summary checks pass |
| 11 | `assurance` | Certification, schema, observability, graph, failures, and plan pass |
| 12 | `finalize` | Replay and final release decision pass |

The runtime repeats the snapshot twice with the same bundle and run identifiers.
The replay receipt records both addresses, the expected address, deterministic
status, and its own content address. Runtime state is `ready` only when every
stage is ready and the replay receipt is accepted.

## Assurance planes

The runtime embeds the following independent assurance planes:

| Plane | Output |
| --- | --- |
| Boundary | 13 public boundary checks |
| Indexes | 7 indexes and 22 conservation checks |
| Reconciliation | 35 cross-domain checks |
| Summary | 20 reviewer-counter checks |
| Certification | 8 planes and 48 checks |
| Schema | 5 resource schemas and 11 shape checks |
| Observability | 193 events and 24 metrics |
| Graph | 189 nodes, 191 edges, one connected component |
| Failure rehearsal | 12 mutation rejection cases and 5 audit checks |
| Plan | 13 ordered steps and 6 plan checks |

The source closures contribute 216 certification checks in their domain
receipts. The aggregate certification is a separate 48-check release decision;
the two denominators remain distinct so composition does not hide a source
failure.

## Reconciliation equations

The aggregate reconciliation checks use explicit equations:

```text
domains = 4
artifacts = 27 + 21 + 56 + 51 = 155
dependencies = 6
gates = 4 × 6 = 24
sources = 5 + 5 + 5 + 5 = 20
records = 16 + 16 + 16 + 16 = 64
evaluation_checks = 80 + 80 + 80 + 120 = 360
closure_stages = 13 + 13 + 13 + 13 = 52
certification_checks = 48 + 48 + 60 + 60 = 216
```

The source closure values are read from each runtime projection. The equations
are expected values, not replacement data. A mismatch is observable in the
reconciliation report and blocks the aggregate release.

## Exact-byte export

The export packet contains 13 JSON artifacts:

```text
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
plan.json
runtime.json
```

Each file is canonical UTF-8 JSON with one trailing newline. The manifest is
written as `manifest.json` and records the relative path, media type, byte
count, content address, and packet acceptance. The verifier reports missing,
changed, and unexpected paths. It does not silently overwrite a changed
artifact during verification.

## CLI operations

All commands accept `--bundle-id`, `--run-id`, and `--output` where applicable.

```powershell
python -m glio_noncode frontier-release-closure
python -m glio_noncode frontier-release-closure-query --resource gates --state passed
python -m glio_noncode frontier-release-closure-schema
python -m glio_noncode frontier-release-closure-boundary --key-inventory
python -m glio_noncode frontier-release-closure-indexes
python -m glio_noncode frontier-release-closure-reconciliation --format markdown
python -m glio_noncode frontier-release-closure-summary --format csv
python -m glio_noncode frontier-release-closure-certification
python -m glio_noncode frontier-release-closure-observability
python -m glio_noncode frontier-release-closure-graph
python -m glio_noncode frontier-release-closure-failures
python -m glio_noncode frontier-release-closure-plan
python -m glio_noncode frontier-release-closure-runtime
python -m glio_noncode frontier-release-closure-export --destination release-export
python -m glio_noncode frontier-release-closure-export-verify release-export
```

Successful commands return zero. A rejected release or failed verification
returns two. Invalid query values return the CLI's standard argument error.

## HTTP operations

The API root is `/v1/frontier-release/closure`. Query parameters mirror the
CLI query surface:

```text
/v1/frontier-release/closure/query?resource=artifacts&domain_id=D15&limit=100
/v1/frontier-release/closure/summary?run_id=review-2026-08-25
/v1/frontier-release/closure/certification?bundle_id=release-candidate
/v1/frontier-release/closure/runtime?bundle_id=release-candidate&run_id=release-001
```

The schema route returns the schema plus its shape audit. Index and summary
routes return their primary report plus audit. Runtime returns the complete
12-stage report. Export returns the packet manifest and artifact metadata;
filesystem writing remains an explicit CLI operation so the HTTP API remains
read-only.

## Failure controls

The negative-control rehearsal covers:

| Case family | Expected result |
| --- | --- |
| Missing domain | Snapshot rejected |
| Duplicate domain | Identity audit fails |
| Missing artifact | Manifest denominator fails |
| Duplicate artifact | Artifact identity audit fails |
| Unsafe path | Boundary audit fails |
| Missing gate | Gate denominator fails |
| Failed gate | Release state blocks |
| Dependency cycle | Ordering audit fails |
| Forbidden terminal key | Public schema fails |
| Certification gap | Certification coverage fails |
| Replay divergence | Determinism gate fails |
| Event denominator drift | Observability audit fails |

These cases are structural controls. They do not mutate a source fixture or
write into an export directory; each case records the expected rejection and
observed rejection as an addressed receipt.

## Verification workflow

The local release workflow is:

1. Run the aggregate runtime with a stable run identifier.
2. Inspect the snapshot and query the resource required for review.
3. Review boundary, reconciliation, summary, certification, and failure reports.
4. Confirm the plan is ordered and all prerequisites are present.
5. Write the exact-byte export packet.
6. Verify the packet in a separate command.
7. Run the focused test file and compile checks.
8. Include the resulting content addresses in the release handoff.

The CI workflow runs the runtime command, writes and verifies an export packet,
and executes `tests.test_frontier_release_closure` in addition to the full
repository test suite.

## Extension rules

Adding a fifth source domain requires a new source runtime contract, a new
domain map entry, updated explicit denominators, dependency rules, gate rules,
schema rows, tests, and documentation. Adding an artifact to an existing
source domain must change the source bundle denominator and aggregate
reconciliation expectation together. No extension may bypass the public
boundary audit, exact-byte export verifier, or deterministic replay gate.

The composition layer is intentionally independent of repository history. It
uses the current source modules and permitted aggregate data only; it does not
derive a framework from another repository.
