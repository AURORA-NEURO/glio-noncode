# Evidence release frontier API

The public API is split into contracts, operations, data, evaluation, and runtime.

```python
from glio_noncode.evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from glio_noncode.evidence_release_frontier_public_data import default_evidence_release_frontier_fixture
from glio_noncode.evidence_release_frontier_runtime import run_evidence_release_runtime

fixture = default_evidence_release_frontier_fixture()
evaluation = evaluate_evidence_release_fixture(fixture)
runtime = run_evidence_release_runtime(fixture, run_id="local-review")
assert evaluation.accepted and runtime.accepted
```

Direct operation calls are useful for a small integration boundary:

```python
from glio_noncode.evidence_release_frontier_operations import (
    evaluate_reclassification,
    evaluate_reproducibility_bundle,
    evaluate_supersession,
    sign_dossier,
    verify_signed_dossier,
)
```

The adapter registry validates required fields before dispatch. The evaluator adds
five checks per row: state, issue, role, integrity, and safety. The positive dossier
row receives an additional verification check, giving 81 checks for 16 rows.

Useful command-line entry points are:

```text
evidence-release-frontier-data-audit
evidence-release-frontier-evaluate
evidence-release-frontier-pipeline
evidence-release-frontier-depth
evidence-release-frontier-quality
evidence-release-frontier-failure-injection
evidence-release-frontier-review-csv
```

All JSON-producing commands support `--output`. The CSV projection is deliberately
limited to record identity, capability, operation, role, state, issue codes, and
content address.
