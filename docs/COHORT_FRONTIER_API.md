# Domain 12 Python API guide

The public Python surface is organized into small modules. Imports from the
module paths are preferred for focused use; the package root also exports the
primary records, reports, and builders.

## Public data

```python
from glio_noncode.cohort_frontier_public_data import (
    audit_cohort_frontier_data,
    default_cohort_frontier_fixture,
    load_cohort_frontier_fixture,
)

fixture = default_cohort_frontier_fixture()
audit = audit_cohort_frontier_data(fixture)
assert audit.accepted
```

`default_cohort_frontier_fixture()` returns the public aggregate fixture. It is
deterministic and has five source receipts and sixteen records. The loader
accepts a JSON path and reconstructs typed source, record, and fixture values.

## Contracts and schema

```python
from glio_noncode.cohort_frontier_contracts import default_cohort_frontier_contracts
from glio_noncode.cohort_frontier_schema import default_cohort_frontier_schema

contracts = default_cohort_frontier_contracts()
schema = default_cohort_frontier_schema()
assert len(contracts.contracts) == 4
assert len(schema.operations) == 4
```

The contract registry exposes `by_operation()` and `issue_codes()`. The schema
manifest exposes `by_operation()` and each operation schema exposes
`field_names()`. Both objects have a content address.

## Evaluation

```python
from glio_noncode.cohort_frontier_fixture_eval import evaluate_cohort_frontier_fixture

evaluation = evaluate_cohort_frontier_fixture(fixture)
assert evaluation.accepted
assert evaluation.passed_checks == 120
```

The evaluation contains 16 executions and 120 checks. Use `execution_map()` for
an ID lookup and `by_operation()` for operation-specific review. An execution
retains state, accepted, issue codes, output, and content address.

For a single record:

```python
from glio_noncode.cohort_frontier_fixture_eval import execute_cohort_frontier_record

execution = execute_cohort_frontier_record(fixture.record_map()["C14-POS-001"])
print(execution.state, execution.issue_codes, execution.content_address)
```

Single-record execution is useful for focused regression tests. Full evaluation
is required before release because global checks cover fixture shape and issue
coverage.

## Policy and reconciliation

```python
from glio_noncode.cohort_frontier_policy import default_cohort_frontier_policy
from glio_noncode.cohort_frontier_reconciliation import reconcile_cohort_frontier

policy = default_cohort_frontier_policy(contracts)
decisions = policy.decide(evaluation)
reconciliation = reconcile_cohort_frontier(fixture, evaluation, policy)
assert reconciliation.reconciled
```

The policy produces one decision per operation. Reconciliation produces one
item per fixture record and compares expected and observed state and issue
codes. Both surfaces retain controls.

## Metrics

```python
from glio_noncode.cohort_frontier_metrics import measure_cohort_frontier

metrics = measure_cohort_frontier(evaluation)
assert len(metrics.metrics) == 11
```

Use `metrics.by_id()` to retrieve a metric. Values have numerators and
denominators where relevant. These are fixture and pipeline metrics, not
population estimates.

## Lineage

```python
from glio_noncode.cohort_frontier_lineage import build_cohort_frontier_lineage

lineage = build_cohort_frontier_lineage(fixture, evaluation)
assert lineage.acyclic
assert len(lineage.edges) == 36
```

The graph connects source receipts and fixture records to execution outputs.
Every record must have a terminal address, including controls.

## Quality gate

```python
from glio_noncode.cohort_frontier_quality_gate import evaluate_cohort_frontier_quality

gate = evaluate_cohort_frontier_quality(
    fixture,
    evaluation,
    contracts,
    schema,
    lineage,
    reconciliation,
)
assert gate.accepted
assert gate.passed_count == 12
```

The quality gate has twelve blocking checks. A failed check exposes its ID,
observed value, required value, and rationale.

## Runtime

```python
from glio_noncode.cohort_frontier_runtime import run_cohort_frontier_runtime

runtime = run_cohort_frontier_runtime(fixture, run_id="review-run")
assert runtime.accepted
assert runtime.stage_ids[0] == "data-audit"
```

Runtime stages are ordered and each stores duration and output address. The run
ID is intentionally caller-controlled and is not part of stable fixture
execution addresses.

## Bundle and release

```python
from glio_noncode.cohort_frontier_bundle import assemble_cohort_frontier_bundle
from glio_noncode.cohort_frontier_release import build_cohort_frontier_release_manifest
from glio_noncode.cohort_frontier_replay import replay_cohort_frontier

bundle = assemble_cohort_frontier_bundle(
    fixture, evaluation, metrics, lineage, reconciliation, policy
)
replay = replay_cohort_frontier(fixture, replay_id="release-replay")
release = build_cohort_frontier_release_manifest(runtime.bundle, gate, replay)
assert release.accepted
```

The runtime bundle may be passed directly to the release builder. If callers
assemble a separate bundle, it must carry the same fixture and surface
addresses used by the gate.

## Replay

```python
from glio_noncode.cohort_frontier_replay import (
    compare_cohort_frontier_replays,
    replay_cohort_frontier,
    replay_cohort_frontier_is_deterministic,
)

first = replay_cohort_frontier(fixture, replay_id="first")
second = replay_cohort_frontier(fixture, replay_id="second")
comparison = compare_cohort_frontier_replays(first, second)
assert comparison.accepted
assert replay_cohort_frontier_is_deterministic(fixture)
```

Replay comparisons ignore only explicitly run-specific receipt fields. A drift
field is a release concern even if the final state remains accepted.

## Scenario and threshold surfaces

```python
from glio_noncode.cohort_frontier_scenario_matrix import build_cohort_frontier_scenario_matrix
from glio_noncode.cohort_frontier_thresholds import build_cohort_frontier_threshold_report

matrix = build_cohort_frontier_scenario_matrix()
thresholds = build_cohort_frontier_threshold_report()
assert len(matrix.scenarios) == 33
assert len(thresholds.probes) == 972
```

The matrix covers operation rows and transport threshold combinations. Threshold
profiles retain the values used for each probe. They are boundary probes, not a
calibration study.

## Artifact inventory and invariants

```python
from glio_noncode.cohort_frontier_artifacts import build_cohort_frontier_artifact_inventory
from glio_noncode.cohort_frontier_checks import (
    cohort_frontier_observation_map,
    run_cohort_frontier_invariants,
)

inventory = build_cohort_frontier_artifact_inventory(
    fixture, evaluation, metrics, lineage, gate, runtime.bundle, release
)
observations = cohort_frontier_observation_map(
    context_preserved=True,
    content_addressed=True,
    positive_control_separated=True,
    parity_visible=True,
    transport_visible=True,
    privacy_visible=True,
    discovery_addressed=True,
    source_receipts=True,
    issue_vocabulary=True,
    replay_stable=True,
)
invariants = run_cohort_frontier_invariants(observations)
assert len(inventory.artifacts) == 7
assert invariants.accepted
```

## Observability

```python
from glio_noncode.cohort_frontier_observability import observe_cohort_frontier

observability = observe_cohort_frontier(runtime, evaluation)
assert len(observability.events) == 26
```

Events are structured summaries of runtime stages, record executions, issue
codes, and release counts. They are not a substitute for full artifacts.

## Review view and exports

```python
from glio_noncode.cohort_frontier_views import build_cohort_frontier_review_view
from glio_noncode.cohort_frontier_exports import (
    export_cohort_frontier_canonical,
    export_cohort_frontier_json,
    export_cohort_frontier_manifest,
    export_cohort_frontier_review_csv,
)

view = build_cohort_frontier_review_view(
    fixture, evaluation, metrics, decisions, release
)
csv_text = export_cohort_frontier_review_csv(view)
release_json = export_cohort_frontier_json(release)
canonical = export_cohort_frontier_canonical(release)
manifest = export_cohort_frontier_manifest(runtime.bundle, release)
```

The view has 16 rows, four accepted rows, and twelve issue rows. The CSV has a
fixed header and one row per fixture record.

## Depth audit

```python
from glio_noncode.cohort_frontier_depth import audit_cohort_frontier_depth

depth = audit_cohort_frontier_depth()
assert depth.accepted
assert depth.passed_count == 19
```

The depth audit ties together counts from source receipts, records, contracts,
schemas, evaluations, lineage, quality, runtime, metrics, scenarios, replay,
and determinism.

## Error handling

Expected caller errors include invalid paths, missing required sections, context
mismatch, empty inputs, and malformed operation payloads. Callers should surface
the exception and preserve the input. A failed data audit must not be converted
into a successful empty report.

## Performance guidance

The default fixture is intentionally small. For larger public aggregate inputs:

- load once and reuse typed records;
- build a map by record ID before repeated lookups;
- avoid serializing full artifacts inside loops;
- compute metrics from one evaluation report;
- reuse the same policy and schema objects;
- write exports once after validation.

Content addresses make caching safe only when the hashed body contains every
semantic input. Do not cache a report using a run ID or wall-clock value unless
that value is intentionally part of the report identity.

## API review checklist

- [ ] Public functions have deterministic default behavior.
- [ ] Records and reports expose `to_dict()`.
- [ ] Stable outputs have content addresses.
- [ ] Empty inputs have explicit issues.
- [ ] Context is exact.
- [ ] Controls remain visible.
- [ ] Policy and quality are separate surfaces.
- [ ] Release uses are explicit.
- [ ] Excluded uses are explicit.
- [ ] Replay is available before publication.
