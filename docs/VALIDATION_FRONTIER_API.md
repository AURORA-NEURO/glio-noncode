# Domain 13 planning Python API

The module family exposes typed public data, operation contracts, execution,
review, release, replay, and depth surfaces.

## Public fixture

```python
from glio_noncode.validation_frontier_public_data import (
    audit_validation_frontier_data,
    default_validation_frontier_fixture,
)

fixture = default_validation_frontier_fixture()
assert audit_validation_frontier_data(fixture).accepted
```

The default fixture contains five source receipts and sixteen records. It is
deterministic and bounded to public aggregate planning.

## Contracts and schema

```python
from glio_noncode.validation_frontier_contracts import default_validation_frontier_contracts
from glio_noncode.validation_frontier_schema import default_validation_frontier_schema

contracts = default_validation_frontier_contracts()
schema = default_validation_frontier_schema()
assert len(contracts.contracts) == 4
assert len(schema.operations) == 4
```

Use `contracts.by_operation()` and `schema.by_operation()` for focused review.
Both manifests have content addresses.

## Evaluation

```python
from glio_noncode.validation_frontier_fixture_eval import evaluate_validation_frontier_fixture

evaluation = evaluate_validation_frontier_fixture(fixture)
assert evaluation.accepted
assert evaluation.passed_checks == 120
```

Use `execution_map()` for a record and `by_operation()` for operation review.
Each execution retains state, accepted, issue codes, output, and address.

For a focused record:

```python
from glio_noncode.validation_frontier_fixture_eval import execute_validation_frontier_record

execution = execute_validation_frontier_record(fixture.record_map()["C03-POS-001"])
```

Full evaluation remains required before release because global checks cover
fixture shape, operation coverage, source boundary, and issue vocabulary.

## Policy and reconciliation

```python
from glio_noncode.validation_frontier_policy import default_validation_frontier_policy
from glio_noncode.validation_frontier_reconciliation import reconcile_validation_frontier

policy = default_validation_frontier_policy(contracts)
decisions = policy.decide(evaluation)
reconciliation = reconcile_validation_frontier(fixture, evaluation, policy)
assert reconciliation.reconciled
```

Policy returns one decision per operation. Reconciliation returns one item per
record and compares state and sorted issue codes.

## Metrics and lineage

```python
from glio_noncode.validation_frontier_metrics import measure_validation_frontier
from glio_noncode.validation_frontier_lineage import build_validation_frontier_lineage

metrics = measure_validation_frontier(evaluation)
lineage = build_validation_frontier_lineage(fixture, evaluation)
assert len(metrics.metrics) == 13
assert len(lineage.edges) == 36
```

Metrics are descriptive fixture values. Lineage includes controls.

## Quality and runtime

```python
from glio_noncode.validation_frontier_quality_gate import evaluate_validation_frontier_quality
from glio_noncode.validation_frontier_runtime import run_validation_frontier_runtime

gate = evaluate_validation_frontier_quality(
    fixture, evaluation, contracts, schema, lineage, reconciliation
)
runtime = run_validation_frontier_runtime(fixture, run_id="planning-review")
assert gate.accepted
assert runtime.accepted
```

The gate has twelve blocking checks and runtime has ten ordered stages.

## Bundle and release

```python
from glio_noncode.validation_frontier_release import build_validation_frontier_release_manifest
from glio_noncode.validation_frontier_replay import replay_validation_frontier

replay = replay_validation_frontier(fixture, replay_id="release-replay")
release = build_validation_frontier_release_manifest(runtime.bundle, gate, replay)
assert release.accepted
```

The release includes allowed and excluded uses. `ready` means the bounded
planning artifact passed its checks, not that an assay has succeeded.

## Scenario and threshold surfaces

```python
from glio_noncode.validation_frontier_scenario_matrix import build_validation_frontier_scenario_matrix
from glio_noncode.validation_frontier_thresholds import build_validation_frontier_threshold_report

matrix = build_validation_frontier_scenario_matrix()
thresholds = build_validation_frontier_threshold_report()
assert len(matrix.scenarios) == 31
assert len(thresholds.probes) == 972
```

These are edge probes, not calibration studies.

## Observability and artifacts

```python
from glio_noncode.validation_frontier_artifacts import build_validation_frontier_artifact_inventory
from glio_noncode.validation_frontier_observability import observe_validation_frontier

observability = observe_validation_frontier(runtime, evaluation)
inventory = build_validation_frontier_artifact_inventory(
    fixture, evaluation, metrics, lineage, gate, runtime, release
)
assert len(observability.events) == 26
assert len(inventory.artifacts) == 7
```

## Review view and exports

```python
from glio_noncode.validation_frontier_exports import export_validation_frontier_review_csv
from glio_noncode.validation_frontier_views import build_validation_frontier_review_view

view = build_validation_frontier_review_view(
    fixture, evaluation, metrics, decisions, release
)
csv_text = export_validation_frontier_review_csv(view)
assert len(view.rows) == 16
assert len(csv_text.splitlines()) == 17
```

## Invariants and depth

```python
from glio_noncode.validation_frontier_checks import (
    run_validation_frontier_invariants,
    validation_frontier_observation_map,
)
from glio_noncode.validation_frontier_depth import audit_validation_frontier_depth

observations = validation_frontier_observation_map(
    context_preserved=True,
    positive_control_separated=True,
    source_receipts=True,
    gap_visible=True,
    route_blockers=True,
    construct_pairs=True,
    limitations_retained=True,
    content_addressed=True,
    replay_stable=True,
    use_boundary=True,
)
assert run_validation_frontier_invariants(observations).accepted
assert audit_validation_frontier_depth().passed_count == 20
```

## Error handling

Loader errors, invalid typed payloads, context mismatches, empty inventories,
empty targets, and malformed sequences should be surfaced and preserved. Do not
convert a failed input into a ready planning package.

## API checklist

- [ ] Fixture is public aggregate.
- [ ] Context is exact.
- [ ] Controls remain visible.
- [ ] States are bounded.
- [ ] Issues are declared.
- [ ] Outputs are addressed.
- [ ] Replay is available.
- [ ] Use boundaries are explicit.
