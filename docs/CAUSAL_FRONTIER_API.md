# Domain 11 Python API reference

## Import surface

The package exports the causal frontier objects from `glio_noncode`. Module
imports remain available for callers that prefer narrow dependencies. The public
surface is immutable dataclasses, deterministic constructors, and pure-ish
evaluation functions that return receipts.

```python
from glio_noncode import (
    CausalFrontierOperation,
    default_causal_frontier_fixture,
    evaluate_causal_frontier_fixture,
)
```

## Fixture API

```python
fixture = default_causal_frontier_fixture()
fixture.fixture_id
fixture.fixture_version
fixture.context_key
fixture.sources
fixture.records
fixture.positive_records
fixture.control_records
fixture.source_map()
fixture.record_map()
fixture.to_dict()
```

`default_causal_frontier_fixture` returns a new immutable object with the same
canonical content address on every run. `source_map` and `record_map` are
convenience indexes and do not mutate the fixture.

## Data audit API

```python
from glio_noncode.causal_frontier_public_data import audit_causal_frontier_data

audit = audit_causal_frontier_data(fixture)
assert audit.accepted
audit.failed_check_ids
```

The audit is useful before evaluation and is included in runtime. It checks
manifest integrity, not operation behavior.

## Contracts API

```python
from glio_noncode.causal_frontier_contracts import default_causal_frontier_contracts

contracts = default_causal_frontier_contracts()
contract = contracts.by_operation(CausalFrontierOperation.POSTERIOR_DECOMPOSITION)
contract.required_payload_fields
contract.issue_vocabulary
contract.prohibited_claims
contracts.issue_codes()
```

The contract registry rejects duplicate operations and incomplete operation
coverage. A new operation must be added to the enum and registry together.

## Schema API

```python
from glio_noncode.causal_frontier_schema import default_causal_frontier_schema

schema = default_causal_frontier_schema()
operation_schema = schema.by_operation(CausalFrontierOperation.SELECTIVE_PREDICTION)
operation_schema.field_names()
operation_schema.issue_codes
```

Schema field specs expose type, requiredness, nullability, semantic role, and
validation text. They are suitable for a CLI manifest or a UI form boundary.

## Evaluation API

```python
from glio_noncode.causal_frontier_fixture_eval import (
    evaluate_causal_frontier_fixture,
    execute_causal_frontier_record,
)

evaluation = evaluate_causal_frontier_fixture(fixture)
execution = execute_causal_frontier_record(fixture.records[0])
```

`execution.accepted` is a derived property. It is true for supported and
published states without an error. `evaluation.accepted` requires every check
to pass. The evaluation stores expected and observed values in each check.

## Replay API

```python
from glio_noncode.causal_frontier_replay import (
    replay_causal_frontier,
    compare_causal_frontier_replays,
)

first = replay_causal_frontier(fixture, replay_id="first")
second = replay_causal_frontier(fixture, replay_id="second")
comparison = compare_causal_frontier_replays(first, second)
assert comparison.accepted
```

Replay IDs are labels. The fixture, evaluation, and execution addresses are
deterministic content receipts.

## Policy API

```python
from glio_noncode.causal_frontier_policy import default_causal_frontier_policy

policy = default_causal_frontier_policy(contracts)
decisions = policy.decide(evaluation)
```

Policy uses positive operation paths to determine release disposition while the
evaluation continues to expose controls. `ALLOW_PUBLICATION` is reserved for a
valid dossier manifest. Supported aggregate outputs are allowed into review,
not promoted into clinical use.

## Lineage API

```python
from glio_noncode.causal_frontier_lineage import build_causal_frontier_lineage

lineage = build_causal_frontier_lineage(fixture, evaluation)
lineage.acyclic
lineage.node_addresses
lineage.terminal_addresses
```

The lineage builder uses source receipts, the fixture address, and execution
addresses. It does not fetch external data.

## Metrics API

```python
from glio_noncode.causal_frontier_metrics import measure_causal_frontier

metrics = measure_causal_frontier(evaluation)
metrics.by_id("overall_check_pass_rate")
```

Metrics retain numerator and denominator. Consumers should not read only the
floating-point value.

## Reconciliation API

```python
from glio_noncode.causal_frontier_reconciliation import reconcile_causal_frontier

reconciliation = reconcile_causal_frontier(fixture, evaluation, policy)
reconciliation.reconciled
reconciliation.mismatched_record_ids
```

Reconciliation is exact. Issue tuples are sorted before comparison and are not
compared as sets, so accidental duplicate or missing codes remain detectable.

## Quality API

```python
from glio_noncode.causal_frontier_quality_gate import evaluate_causal_frontier_quality

quality = evaluate_causal_frontier_quality(
    fixture,
    evaluation,
    contracts,
    schema,
    lineage,
    reconciliation,
)
quality.accepted
quality.passed_count
quality.blocking_check_ids
```

Quality checks are blocking in the current release boundary. A future policy can
add a warning check, but it must not silently remove the existing checks.

## Runtime API

```python
from glio_noncode.causal_frontier_runtime import run_causal_frontier_runtime

runtime = run_causal_frontier_runtime(fixture, run_id="api-run")
runtime.stage_ids
runtime.bundle
runtime.accepted
```

The runtime uses ten stages. The returned bundle is ready to bind into a release
manifest only when its policy decisions and gate receipts are accepted.

## Release API

```python
from glio_noncode.causal_frontier_release import build_causal_frontier_release_manifest

release = build_causal_frontier_release_manifest(runtime.bundle, quality, first)
release.state
release.allowed_uses
release.excluded_uses
```

The release manifest keeps the boundary next to the addresses it governs. A
ready state does not widen the boundary.

## View and export API

```python
from glio_noncode.causal_frontier_views import build_causal_frontier_review_view
from glio_noncode.causal_frontier_exports import (
    export_causal_frontier_json,
    export_causal_frontier_review_csv,
)

view = build_causal_frontier_review_view(
    fixture,
    evaluation,
    metrics,
    decisions,
    release,
)
json_text = export_causal_frontier_json(release)
csv_text = export_causal_frontier_review_csv(view)
```

The view has 16 rows. The CSV is a projection and does not replace the nested
JSON receipt.

## Adapter API

```python
from glio_noncode.causal_frontier_adapters import default_causal_frontier_adapters

adapters = default_causal_frontier_adapters()
adapter = adapters.by_operation(CausalFrontierOperation.SELECTIVE_PREDICTION)
receipt = adapter.normalize(
    [{"prediction_id": "p1", "score": 0.8, "uncertainty": 0.1}],
    context_key=fixture.context_key,
)
```

Adapters normalize only declared fields and enforce exact context. They do not
execute scientific calculations; that remains in the operation layer.

## Threshold API

```python
from glio_noncode.causal_frontier_thresholds import build_causal_frontier_threshold_report

thresholds = build_causal_frontier_threshold_report()
thresholds.accepted_probes
thresholds.review_probes
```

The report contains 324 probes over four operation profiles and multiple score,
uncertainty, support, and evidence-count boundaries.

## Artifact API

```python
from glio_noncode.causal_frontier_artifacts import build_causal_frontier_artifact_inventory

inventory = build_causal_frontier_artifact_inventory(
    fixture,
    evaluation,
    metrics,
    lineage,
    quality,
    runtime.bundle,
    release,
)
inventory.root_artifact_id
inventory.total_bytes
```

The inventory holds seven artifact kinds and connects each artifact to parent
addresses. It is an in-memory manifest; persistence is left to the caller.

## Invariant API

```python
from glio_noncode.causal_frontier_checks import (
    causal_frontier_observation_map,
    run_causal_frontier_invariants,
)

observations = causal_frontier_observation_map(
    context_preserved=True,
    content_addressed=True,
    positive_control_separated=True,
    bounded_posterior=True,
    support_threshold_visible=True,
    abstention_visible=True,
    dossier_addressed=True,
    source_receipts=True,
    issue_vocabulary=True,
    replay_stable=True,
)
invariants = run_causal_frontier_invariants(observations)
```

The invariant report has ten named checks and returns failed IDs. Extension
modules can use the same mechanism without changing the core evaluator.

## Error behavior

Direct adapter methods raise typed validation errors on malformed input. Fixture
evaluation catches expected validation errors and returns invalid execution
receipts so controls can be evaluated in one pass. Callers should preserve the
error string and record ID when handling invalid receipts.

## Type stability

Enums serialize to their values, tuples serialize as arrays, dataclasses become
objects, and content addresses are strings. Consumers should use `to_dict()` or
the export helpers rather than relying on dataclass implementation details.

## Compatibility guidance

The public aggregate boundary is versioned by fixture, schema, and release.
Adding a field can be compatible when optional and ignored by old consumers;
renaming a field, changing a state, changing an issue code, or changing a
threshold is behavior-significant.

## Minimal API smoke test

```python
fixture = default_causal_frontier_fixture()
evaluation = evaluate_causal_frontier_fixture(fixture)
assert evaluation.accepted
assert len(evaluation.checks) == 120
```

This smoke test is intentionally small. The focused test files and CI commands
cover the complete release path.
