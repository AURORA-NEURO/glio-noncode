# Workspace frontier API surface

## Public module map

The frontier is split into narrow modules so each concern can be inspected and
replayed independently.

| Module | Responsibility |
| --- | --- |
| `workspace_frontier_public_data` | fixture, source receipts, catalog, audit |
| `workspace_frontier_fixture_eval` | typed surface execution and checks |
| `workspace_frontier_contracts` | input, output, state, and issue contracts |
| `workspace_frontier_schema` | field-level schema manifest |
| `workspace_frontier_adapters` | input inspection and receipts |
| `workspace_frontier_replay` | deterministic replay comparison |
| `workspace_frontier_scenario_matrix` | independent scenario coverage |
| `workspace_frontier_policy` | research-use decisions |
| `workspace_frontier_lineage` | acyclic source-to-execution graph |
| `workspace_frontier_reconciliation` | expected-to-observed comparison |
| `workspace_frontier_metrics` | descriptive fixture metrics |
| `workspace_frontier_quality_gate` | release-quality checks |
| `workspace_frontier_runtime` | ordered stage report |
| `workspace_frontier_bundle` | composed release inputs |
| `workspace_frontier_release` | ready or hold manifest |
| `workspace_frontier_observability` | structured stage and execution events |
| `workspace_frontier_views` | review rows |
| `workspace_frontier_exports` | JSON, canonical, manifest, CSV |
| `workspace_frontier_depth` | 21-check depth audit |
| `workspace_frontier_thresholds` | 972 bounded probes |
| `workspace_frontier_artifacts` | seven-artifact inventory |
| `workspace_frontier_checks` | ten invariant definitions |
| `workspace_frontier_review_queue` | held and ready review rows |

## Python import example

```python
from glio_noncode.workspace_frontier_fixture_eval import (
    evaluate_workspace_frontier_fixture,
)
from glio_noncode.workspace_frontier_public_data import (
    default_workspace_frontier_fixture,
)

fixture = default_workspace_frontier_fixture()
evaluation = evaluate_workspace_frontier_fixture(fixture)
assert evaluation.accepted
```

## Case projection

The existing `CaseWorkspaceBuilder` remains the source of case record
construction. The frontier evaluator supplies typed `ReferenceContext`,
`VariantIdentity`, `CandidateElement`, and `CaseManifest` values. This keeps
the evidence package close to the product primitive.

The projection returns:

- workspace identity;
- context key;
- state;
- record count;
- ordered section IDs;
- record IDs;
- complete-match page count;
- deterministic facets;
- warnings;
- accessibility metadata;
- input content address.

## Cohort projection

The cohort projection follows four typed steps:

1. convert payload rows to `CohortVariantRecord`;
2. construct a `CohortQuery`;
3. build a `CohortQueryResult`;
4. assemble `CohortDiscoveryEvidence` and `ResearchWorkspace`.

The output retains `excluded_count` and `excluded_reasons`. Clients should show
these fields near the selected row count so a user can tell an empty selection
from a source with no records.

## Variant detail projection

The detail operation accepts a workspace and one variant ID. It returns a
`VariantDetail` with the containing workspace ID, requested ID, state, optional
variant record, declared related IDs, typed related groups, warnings, and an
address. The operation does not search other workspaces.

## Track projection

The track operation converts a `RegulatoryTrackBatch` to a workspace. Each
record retains feature type, score, strand, genome build, attributes, source
line, and raw hash. The browser can then use the common `WorkspaceQuery` for
text, type, source, state, chromosome, interval, tags, and pagination.

## Contract registry

`default_workspace_frontier_contracts()` returns four contracts. Each contract
declares required inputs, required outputs, state values, issue codes, and a
research boundary. Use `by_operation()` to select a contract and
`issue_codes()` to obtain the union vocabulary.

## Schema registry

`default_workspace_frontier_schema()` returns four operation schemas. Each
field includes value type, required flag, nullable flag, semantic role, and
content address. Use `fields()` to inspect the flattened field inventory.

## Policy

`default_workspace_frontier_policy()` defines allowed and excluded uses. Call
`policy.decide(evaluation)` to obtain one decision per execution. Supported
positive paths without issues are research-view ready. Every other state is
held or withheld.

## Review view

`build_workspace_frontier_review_view()` joins fixture source counts,
evaluation executions, policy decisions, and the release manifest. The result
has one row per fixture record. `accepted_rows()` returns ready rows;
`issue_rows()` returns rows with issue codes; `by_operation()` narrows by
surface.

## Exports

Use `export_workspace_frontier_json()` for readable JSON,
`export_workspace_frontier_canonical()` for stable canonical JSON,
`export_workspace_frontier_manifest()` for a compact handoff object, and
`export_workspace_frontier_review_csv()` for a row-oriented review file.

All JSON exports include a trailing newline. CSV exports include a header.

## Extension rules

When adding a fifth operation:

1. add an operation enum value;
2. add a positive and three controls;
3. implement execution mapping;
4. add a contract and schema;
5. add scenario and threshold coverage;
6. add policy and review behavior;
7. add lineage, metrics, quality, runtime, artifact, and export handling;
8. add CLI parser and dispatch;
9. add registry evidence;
10. add docs and CI steps.

Do not add an operation only to the evaluator. A surface is not complete until
its inputs, outputs, controls, release evidence, tests, and operational paths
agree.

## Stable ordering rules

Fixture rows remain in operation order and record ID order. Evaluations preserve
fixture order. Workspace search sorts by record type, label, and record ID.
Metrics use a declared tuple order. Runtime stages use ascending sequence.
Artifacts list dependency-safe order. Review rows preserve evaluation order.

## Error handling rules

Typed model failures become declared invalid issue codes only at the evaluator
boundary. Direct public primitives continue to raise their typed validation
exceptions. This keeps low-level callers strict while giving the fixture a
stable control vocabulary.

## Context handling rules

Never strip, lower, or partially compare a context key at a release boundary.
Chromosome normalization is allowed inside interval matching because it is a
coordinate normalization, not a context relaxation.

## Address handling rules

Call `content_hash()` on typed bodies before adding runtime wrapper fields.
Runtime reports may include run IDs, but deterministic evaluation addresses
must remain replayable. A content address is a receipt, not a secret.

## API maturity

This is a research infrastructure API. It is suitable for deterministic tests,
bounded CLI output, review exports, and future clients. It is not a promise of
production service availability, visual component behavior, external identity,
or clinical interpretation.
