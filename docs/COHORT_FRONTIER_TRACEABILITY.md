# Domain 12 traceability map

This map links the four verified capabilities to implementation modules,
fixtures, tests, commands, and release artifacts. It is a compact navigation
aid for maintenance and review.

## C13 subgroup fairness

Implementation:

- `frontier_inference_alpha.SubgroupFairnessStratifier`;
- `frontier_inference_alpha.FairnessStratificationReport`;
- `cohort_frontier_public_data`;
- `cohort_frontier_fixture_eval`;
- `cohort_frontier_quality_gate`;
- `cohort_frontier_release`.

Evidence:

- positive balanced strata;
- high-gap control;
- empty-input control;
- missing-group control;
- review ID preservation;
- CSV and release inclusion.

Tests:

- `tests.test_frontier_inference_alpha`;
- `tests.test_cohort_frontier_evidence`;
- `tests.test_cohort_frontier_depth`;
- `tests.test_cohort_frontier_evidence_cli`.

Commands:

- `cohort-frontier-evaluate`;
- `cohort-frontier-quality-gate`;
- `export-cohort-frontier-review-csv`.

## C14 transportability

Implementation:

- `frontier_inference_alpha.TransportabilityEstimator`;
- `frontier_inference_alpha.TransportabilityReport`;
- `cohort_frontier_scenario_matrix`;
- `cohort_frontier_thresholds`;
- `cohort_frontier_replay`.

Evidence:

- complete-overlap positive;
- target-feature-gap control;
- high-shift control;
- empty-input control;
- 33 scenario rows;
- 972 threshold probes.

Tests:

- `tests.test_frontier_inference_alpha`;
- `tests.test_cohort_frontier_evidence`;
- `tests.test_cohort_frontier_depth`;
- `tests.test_cohort_frontier_evidence_cli`.

Commands:

- `cohort-frontier-evaluate`;
- `cohort-frontier-metrics`;
- `cohort-frontier-replay`;
- `cohort-frontier-depth-audit`.

## C15 federated summary

Implementation:

- `frontier_inference_alpha.FederatedSummaryAnalyzer`;
- `frontier_inference_alpha.FederatedSummaryReport`;
- `cohort_frontier_adapters`;
- `cohort_frontier_contracts`;
- `cohort_frontier_policy`.

Evidence:

- two-site positive summary;
- privacy-floor control;
- empty-input control;
- malformed-mean control;
- aggregate-only export;
- policy and gate preservation.

Tests:

- `tests.test_frontier_inference_alpha`;
- `tests.test_frontier_inference_alpha_cli`;
- `tests.test_cohort_frontier_evidence`;
- `tests.test_cohort_frontier_depth`;
- `tests.test_cohort_frontier_evidence_cli`.

Commands:

- `cohort-frontier-evaluate`;
- `cohort-frontier-policy`;
- `cohort-frontier-quality-gate`.

## C16 cohort discovery

Implementation:

- `frontier_inference_alpha.CohortDiscoveryPublisher`;
- `frontier_inference_alpha.CohortDiscoveryBundle`;
- `cohort_frontier_bundle`;
- `cohort_frontier_lineage`;
- `cohort_frontier_views`;
- `cohort_frontier_exports`.

Evidence:

- aggregate feature publication;
- context-mismatch control;
- empty-input control;
- empty-analysis control;
- seven-node artifact inventory;
- 16-row review view.

Tests:

- `tests.test_frontier_inference_alpha`;
- `tests.test_cohort_frontier_evidence`;
- `tests.test_cohort_frontier_depth`;
- `tests.test_cohort_frontier_evidence_cli`.

Commands:

- `cohort-frontier-bundle`;
- `cohort-frontier-release`;
- `export-cohort-frontier-review-csv`.

## Shared surfaces

| Surface | Module | Default count |
| --- | --- | ---: |
| public data | cohort_frontier_public_data | 5 sources, 16 records |
| contracts | cohort_frontier_contracts | 4 contracts |
| schema | cohort_frontier_schema | 4 schemas |
| evaluation | cohort_frontier_fixture_eval | 120 checks |
| replay | cohort_frontier_replay | 120 stable checks |
| metrics | cohort_frontier_metrics | 11 metrics |
| lineage | cohort_frontier_lineage | 36 edges |
| policy | cohort_frontier_policy | 4 decisions |
| quality | cohort_frontier_quality_gate | 12 checks |
| runtime | cohort_frontier_runtime | 10 stages |
| release | cohort_frontier_release | 4 checks |
| depth | cohort_frontier_depth | 19 checks |

## Files and responsibility

| File family | Responsibility |
| --- | --- |
| public_data | typed aggregate fixture and source audit |
| contracts | required fields and issue vocabulary |
| fixture_eval | operation dispatch and check accounting |
| replay | stable receipt comparison |
| scenario_matrix | boundary combinations |
| policy | research-use decisions |
| lineage | source and record graph |
| reconciliation | expected versus observed state |
| metrics | coverage and state counts |
| bundle | release surface assembly |
| schema | field and validation manifest |
| quality_gate | blocking checks |
| runtime | ordered rehearsal |
| release | release state and use lists |
| observability | event and counter summary |
| views | row-level review representation |
| exports | JSON, canonical, manifest, and CSV output |
| depth | cross-surface invariant counts |
| adapters | external aggregate input boundary |
| thresholds | threshold probe inventory |
| artifacts | artifact inventory and root |
| checks | invariant runner and observation map |

## CI trace

The workflow invokes each release surface after the full test suite. The command
names are intentionally parallel to module responsibilities so a CI failure can
be mapped directly to a file family.

| CI step | Primary proof |
| --- | --- |
| data boundary audit | source and fixture shape |
| contracts | operation vocabulary |
| schema | field coverage |
| fixture evaluation | positive and control behavior |
| replay | deterministic receipts |
| metrics | state accounting |
| lineage | complete acyclic graph |
| policy | bounded decisions |
| quality gate | blocking release checks |
| runtime | ordered integration |
| bundle | release assembly |
| release | ready-state checks |
| review CSV | all-row handoff |
| depth audit | aggregate depth proof |

## Change impact guide

Changes to the underlying primitive require evaluation, replay, reconciliation,
quality, and capability evidence review. Changes to issue mappings require
contracts, schema, controls, and failure documentation review. Changes to export
columns require schema, CLI, CI, and downstream handoff review. Changes to
source receipts require the data audit and public-boundary review.

## Completion criteria

A C13-C16 capability remains verified only while its implementation modules,
fixture evidence, tests, command surface, and release evidence remain present.
Deleting a control test or narrowing the review view may make a local run look
clean while reducing the actual evidence boundary; such a change requires
explicit review.
