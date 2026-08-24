# D15 Workbench Architecture

D15 is the public aggregate architecture for case workspaces, cohort workspaces, variant exploration, regulatory tracks, scientific workbench views, collaboration controls, and release-facing review surfaces. It binds four accepted delegate families behind one typed and deterministic aggregate boundary.

The module is descriptive research infrastructure. It does not create a patient record, make a clinical decision, assert efficacy, infer causality, or choose a treatment. Payloads are sanitized at the aggregate boundary and held states remain visible for review.

## Completion surface

The checked-in fixture is `workbench-architecture-public-aggregate-001`.

| Measure | Count | Closure rule |
| --- | ---: | --- |
| Public source receipts | 20 | Four delegate source registries are namespaced and addressed |
| D15 operations | 16 | One operation per C01-C16 capability |
| Cases | 64 | One positive and three controls per operation |
| Positive cases | 16 | Delegate positive result retained without state promotion |
| Control cases | 48 | Context, invalid, absent, incomplete, blocked, and review paths retained |
| Evaluation checks | 458 | Seven checks per case plus ten global checks |
| Ledger events | 80 | Sixteen operation declarations plus sixty-four executions |
| Projection artifacts | 6 | Fixture, sources, evaluation, review, lineage, and metrics/ledger |
| Runtime stages | 24 | Load through final addressed runtime |
| Quality checks | 10 | Audit, plan, evaluation, replay, artifacts, metrics, lineage, release, ledger, state coverage |

## Delegate families

| Family | Capability range | Plane | Sources | Records | Context |
| --- | --- | --- | ---: | ---: | --- |
| `workspace_frontier` | C01-C04 | `workspace_foundation` | 5 | 16 | `GRCh38\|glioma\|adult\|stem_like\|core\|untreated` |
| `workspace_beta_frontier` | C05-C08 | `workspace_beta` | 5 | 16 | `GRCh38\|glioma\|adult\|stem_like\|core\|untreated` |
| `workspace_gamma_frontier` | C09-C12 | `workspace_collaboration` | 5 | 16 | `GRCh38\|glioma\|adult\|stem_like\|core\|untreated` |
| `workbench_release_frontier` | C13-C16 | `workbench_release` | 5 | 16 | `GRCh38\|glioma\|adult\|stem_like\|tumor_core\|pre_treatment` |

The aggregate context is `multi_context_public_aggregate`. A foreign family context is retained as a control only when an explicit `context_mismatch` issue is present in the delegate result.

## Operation matrix

| Capability | Operation | Family | Output |
| --- | --- | --- | --- |
| C01 | `case_workspace` | foundation | case workspace view |
| C02 | `cohort_workspace` | foundation | cohort workspace view |
| C03 | `variant_explorer` | foundation | variant explorer view |
| C04 | `regulatory_track_browser` | foundation | regulatory track view |
| C05 | `topology_viewer` | beta | topology viewport |
| C06 | `causal_chain_explorer` | beta | causal chain view |
| C07 | `posterior_decomposition` | beta | posterior decomposition |
| C08 | `evidence_table` | beta | evidence table view |
| C09 | `validation_experiment_board` | collaboration | experiment board |
| C10 | `notebook_sdk_launcher` | collaboration | launch plan |
| C11 | `signed_snapshot` | collaboration | shareable snapshot |
| C12 | `role_collaboration` | collaboration | access report |
| C13 | `structured_review` | release | review projection |
| C14 | `report_export` | release | report artifact |
| C15 | `search_palette` | release | search result view |
| C16 | `accessibility_human_factors` | release | interface assessment |

Every operation retains input and output contracts, family and plane, source joins, dependencies, control policy, and content address. The plan validator requires all dependencies to resolve to earlier nodes and requires four cases per operation.

## Scenario and state coverage

The foundation family includes partial workspaces, supported cohort and variant views, absent matches, abstained variant lookup, invalid inputs, and foreign contexts. The beta family includes supported topology, complete causal chains, incomplete mediator paths, contradictory mediators, partial posterior components, unreconciled components, and absent tables. The collaboration family includes blocked experiment dependencies, review-ready launch plans, verified snapshots, expired snapshots, allowed access, and denied members. The release family includes reviewed forms, exported reports, searched records, passed criteria, missing fields, duplicate sections, no matches, invalid payloads, blocked contexts, expired snapshots, and failed criteria.

Positive labels identify the delegate’s positive fixture row. They do not imply a successful state. For example, the C01 positive is `partial`, the C09 positive is `blocked`, and the C13 positive is `reviewed`. This preserves the actual behavior of the delegate families.

## Evaluation accounting

Each case receives checks for state, exact issue codes, bounded counts, operation join, source joins, family context, and addressed receipt. Ten global checks close total case count, positive count, control distribution, family balance, operation balance, source coverage, explicit states, output addresses, context controls, and receipt coverage.

The accepted evaluation requires all 458 checks to pass. The output address and receipt address are deterministic over the normalized result. A missing delegate record becomes an invalid execution with `missing_delegate_record`; it is never dropped from the result set.

## Public payload boundary

The aggregate normalizer removes restricted identity and decision keys from payload projections before writing the checked-in fixture. The compliance module traverses nested dictionaries and sequences, verifies public source flags, verifies case addresses, and verifies non-empty delegate contexts.

The release limitations remain in the release object and report:

- workbench rows are public aggregate receipts and bounded views;
- workspace states are not efficacy, causal, or clinical decisions;
- held, blocked, denied, rejected, and abstained paths remain visible;
- external review and institutional controls remain outside the release.

## Runtime and projections

The runtime has twenty-four addressed stages:

1. fixture load, source audit, schema validation, and plan compilation;
2. foundation, beta, collaboration, and release family readiness;
3. case execution, review routing, lineage linking, and ledger closure;
4. metrics, replay, artifacts, and bundle closure;
5. release, quality, depth, and compliance;
6. controls, report, runtime seed, and final address.

The review queue includes all controls and any positive result outside the successful-state set. The ledger appends operation declaration events followed by case execution events. Six artifacts provide separate public, review, lineage, and metrics projections.

## Python surface

The stable surface is `glio_noncode.workbench_architecture_exports`, and the package root re-exports the D15 symbols.

```python
from glio_noncode.workbench_architecture_runtime import run_workbench_architecture

runtime = run_workbench_architecture()
assert runtime.accepted
assert len(runtime.evaluation.checks) == 458
```

Primary functions are `default_workbench_architecture_fixture`, `audit_workbench_architecture_data`, `build_workbench_architecture_plan`, `evaluate_workbench_architecture_fixture`, `build_workbench_architecture_review_queue`, `workbench_architecture_lineage_rows`, `build_workbench_architecture_ledger`, `workbench_architecture_metrics`, `replay_workbench_architecture_fixture`, `build_workbench_architecture_artifacts`, `build_workbench_architecture_release`, `assess_workbench_architecture_quality`, `assess_workbench_architecture_compliance`, `deep_audit_workbench_architecture`, `query_workbench_architecture`, and `run_workbench_architecture`.

## Verification commands

```text
python -m glio_noncode workbench-architecture-fixture --output data/workbench-architecture-public-aggregate.json
python -m glio_noncode workbench-architecture-data-audit --input data/workbench-architecture-public-aggregate.json --output /tmp/workbench-data.json
python -m glio_noncode evaluate-workbench-architecture --input data/workbench-architecture-public-aggregate.json --output /tmp/workbench-evaluation.json
python -m glio_noncode workbench-architecture-runtime --input data/workbench-architecture-public-aggregate.json --output /tmp/workbench-runtime.json
python -m glio_noncode workbench-architecture-query --input data/workbench-architecture-public-aggregate.json --operation D15-C14 --output /tmp/workbench-query.json
python -m unittest tests.test_workbench_architecture tests.test_workbench_architecture_exports tests.test_workbench_architecture_reporting tests.test_workbench_architecture_cli
```
