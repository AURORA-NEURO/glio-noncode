# Editing-design frontier API

## Direct operations

```python
from glio_noncode import (
    evaluate_crispr_design,
    evaluate_base_editing,
    evaluate_prime_editing,
    evaluate_allele_reporter,
)

crispr = evaluate_crispr_design(payload)
base = evaluate_base_editing(payload)
prime = evaluate_prime_editing(payload)
reporter = evaluate_allele_reporter(payload)
```

Every payload carries an exact context key and explicit controls/readouts. Operation-specific output contains candidate windows or design package manifests, with no private fields.

## Fixture and runtime

```python
from glio_noncode import (
    default_editing_design_frontier_fixture,
    evaluate_editing_design_fixture,
    run_editing_design_runtime,
)

fixture = default_editing_design_frontier_fixture()
evaluation = evaluate_editing_design_fixture(fixture)
runtime = run_editing_design_runtime(fixture, run_id="local-editing-review")
assert runtime.accepted
```

The adapters apply schema checks before operation dispatch. An incomplete payload is rejected with `schema_invalid`.
