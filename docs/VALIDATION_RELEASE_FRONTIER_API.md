# Validation-release frontier API

The public Python API is organized by concern. Each object is immutable and
serializes through `to_dict()` with a `content_address` where the object is a
release or evidence receipt.

## Fixture and evaluation

```python
from glio_noncode.validation_release_frontier_public_data import (
    default_validation_release_frontier_fixture,
)
from glio_noncode.validation_release_frontier_fixture_eval import (
    evaluate_validation_release_fixture,
)

fixture = default_validation_release_frontier_fixture()
evaluation = evaluate_validation_release_fixture(fixture)
assert evaluation.accepted
assert len(evaluation.checks) == 80
```

`ValidationReleaseFixture` contains five public source receipts and sixteen
operation records. Four are positive paths and twelve are controls. A record
contains its operation, role, exact context, source IDs, payload, expected
state, expected issue codes, notes, and content address.

## Operation dispatch

```python
from glio_noncode.validation_release_frontier_operations import (
    run_validation_release_operation,
)
from glio_noncode.validation_release_frontier_contracts import (
    ValidationReleaseOperation,
)

result = run_validation_release_operation(
    ValidationReleaseOperation.OFF_TARGET_RISK,
    {
        "target_id": "guide-1",
        "context_key": fixture.context_key,
        "on_target_score": 0.9,
        "off_targets": [{"candidate_id": "alt-1", "score": 0.04, "weight": 1.0}],
    },
)
print(result.state, result.issue_codes, result.output)
```

The four operation functions are independently callable. They return a state,
normalized issue codes, a safe output projection, and a content address. Input
shape failures are returned as `rejected` results by the top-level dispatcher.

## Runtime and release

```python
from glio_noncode.validation_release_frontier_runtime import (
    run_validation_release_runtime,
)

runtime = run_validation_release_runtime(run_id="local-validation-release")
assert runtime.accepted
assert len(runtime.stages) == 50
assert runtime.release_checks.passed
assert runtime.bundle.accepted
```

The runtime is a local rehearsal. It does not fetch public URLs while
replaying the checked-in fixture. The release bundle contains only receipt
addresses, counts, states, issue codes, and review projections.

## Review and exports

```python
from glio_noncode.validation_release_frontier_review_queue import (
    build_validation_release_review_queue,
)
from glio_noncode.validation_release_frontier_exports import (
    export_validation_release_review_csv,
)

queue = build_validation_release_review_queue(evaluation)
csv_text = export_validation_release_review_csv(evaluation)
```

Controls remain reviewable or blocked. The queue does not discard negative
evidence, and CSV/Markdown exports are deterministic projections rather than
new scientific assertions.
