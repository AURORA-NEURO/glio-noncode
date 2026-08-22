# Domain 13 planning traceability map

This map connects the four verified capabilities to implementation, evidence,
tests, commands, and release artifacts.

## C01 evidence gap

Implementation:

- `validation_planning.EvidenceGapAnalyzer`;
- `validation_frontier_public_data`;
- `validation_frontier_fixture_eval`;
- `validation_frontier_quality_gate`;
- `validation_frontier_release`.

Evidence:

- missing measurement;
- high uncertainty;
- context mismatch;
- missing hypothesis;
- complete-snapshot control;
- ranked priority order.

Tests:

- `tests.test_validation_planning`;
- `tests.test_validation_frontier_evidence`;
- `tests.test_validation_frontier_depth`;
- `tests.test_validation_frontier_evidence_cli`.

## C02 assay eligibility

Implementation:

- `validation_planning.AssayEligibilityRouter`;
- `validation_frontier_contracts`;
- `validation_frontier_policy`;
- `validation_frontier_reconciliation`.

Evidence:

- matching model and bounds;
- model mismatch;
- missing controls;
- missing readouts;
- empty inventory abstention;
- alternatives and sensitivity.

Tests are the same focused planning and frontier modules listed for C01.

## C03 MPRA planning

Implementation:

- `validation_planning.MPRAPlanner`;
- `validation_frontier_schema`;
- `validation_frontier_scenario_matrix`;
- `validation_frontier_thresholds`.

Evidence:

- reference and alternate constructs;
- exact context;
- allele pairing;
- context mismatch;
- construct budget;
- empty target list.

## C04 STARR-seq planning

Implementation:

- `validation_planning.STARRSeqPlanner`;
- `validation_frontier_bundle`;
- `validation_frontier_lineage`;
- `validation_frontier_exports`.

Evidence:

- STARR-seq assay identity;
- reference and alternate constructs;
- insert bound;
- context mismatch;
- empty target list;
- aggregate review manifest.

## Shared surfaces

| Surface | Module | Default count |
| --- | --- | ---: |
| public data | validation_frontier_public_data | 5 sources, 16 records |
| contracts | validation_frontier_contracts | 4 contracts |
| schema | validation_frontier_schema | 4 schemas |
| evaluation | validation_frontier_fixture_eval | 120 checks |
| replay | validation_frontier_replay | 120 stable checks |
| scenarios | validation_frontier_scenario_matrix | 31 rows |
| thresholds | validation_frontier_thresholds | 972 probes |
| metrics | validation_frontier_metrics | 13 rows |
| lineage | validation_frontier_lineage | 36 edges |
| policy | validation_frontier_policy | 4 decisions |
| quality | validation_frontier_quality_gate | 12 checks |
| runtime | validation_frontier_runtime | 10 stages |
| observability | validation_frontier_observability | 26 events |
| artifacts | validation_frontier_artifacts | 7 nodes |
| release | validation_frontier_release | 4 checks |
| depth | validation_frontier_depth | 20 checks |

## Command trace

| Command | Proof |
| --- | --- |
| validation-frontier-data-audit | source and fixture shape |
| validation-frontier-contracts | operation vocabulary |
| validation-frontier-schema | field coverage |
| validation-frontier-evaluate | positive and control behavior |
| validation-frontier-replay | stable receipts |
| validation-frontier-metrics | state accounting |
| validation-frontier-lineage | complete graph |
| validation-frontier-policy | bounded planning decisions |
| validation-frontier-quality-gate | blocking checks |
| validation-frontier-runtime | ordered integration |
| validation-frontier-observability | events and counters |
| validation-frontier-artifacts | release inventory |
| validation-frontier-bundle | connected review bundle |
| validation-frontier-release | release state |
| export-validation-frontier-review-csv | all-row handoff |
| validation-frontier-depth-audit | cross-surface depth |

## Change impact

Changing the underlying planner affects fixture evaluation, replay,
reconciliation, quality, release, tests, and capability evidence. Changing an
issue mapping affects contracts, controls, schema, failure documentation, and
CSV review. Changing target or constraint fields affects schema, API, CLI, and
data dictionary. Changing sources affects boundary audit and lineage.

## Verification rule

C01–C04 remain verified only while their implementation, positive path, control
path, tests, CLI commands, and release evidence remain present. Removing a
control or filtering blocked rows reduces evidence coverage and needs explicit
review.
