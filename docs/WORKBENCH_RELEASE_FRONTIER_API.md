# Workbench release frontier API

```python
from glio_noncode.workbench_release_frontier_public_data import default_workbench_release_frontier_fixture
from glio_noncode.workbench_release_frontier_fixture_eval import evaluate_workbench_release_fixture
from glio_noncode.workbench_release_frontier_runtime import run_workbench_release_runtime

fixture = default_workbench_release_frontier_fixture()
evaluation = evaluate_workbench_release_fixture(fixture)
runtime = run_workbench_release_runtime(fixture, run_id="local-workbench-review")
assert evaluation.accepted and runtime.accepted
```

Direct operations are available from `workbench_release_frontier_operations`:

- `evaluate_review_form`
- `evaluate_report_export`
- `evaluate_search_palette`
- `evaluate_accessibility`
- `run_workbench_release_operation`

The adapter registry validates required fields before dispatch. The evaluator emits
five checks per row: state, issue, role, integrity, and safety. With 16 rows this
produces 80 checks. Public JSON output omits private marker fields from operation
projections.

## CLI

```text
workbench-release-frontier-data-audit
workbench-release-frontier-evaluate
workbench-release-frontier-pipeline
workbench-release-frontier-depth
workbench-release-frontier-quality
workbench-release-frontier-handoff
workbench-release-frontier-access
workbench-release-frontier-data-dictionary
workbench-release-frontier-report
workbench-release-frontier-failure-injection
workbench-release-frontier-review-csv
```

All JSON commands accept `--output`. The CSV projection uses stable columns and
contains only row identity, capability, operation, role, state, issue codes, and
content address.
