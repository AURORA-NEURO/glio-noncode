# Validation-design frontier API

## Core contracts

`ValidationDesignOperation` enumerates `gap_analysis`, `assay_eligibility`, `mpra_package`, and `starrseq_package`.

`ValidationDesignOperationResult` contains:

- operation
- state
- normalized issue codes
- safe output projection
- content address

`ValidationDesignRecord` adds the capability, role, context, source joins, expected outcome, and fixture note. `ValidationDesignEvaluation` contains one execution and five checks for every record.

## Operation calls

```python
from glio_noncode import (
    evaluate_gap_analysis,
    evaluate_assay_eligibility,
    evaluate_mpra_package,
    evaluate_starrseq_package,
)

gap = evaluate_gap_analysis(payload)
route = evaluate_assay_eligibility(payload)
mpra = evaluate_mpra_package(payload)
starr = evaluate_starrseq_package(payload)
```

All payloads must carry the exact fixture context key when used in the public scenario. The four adapter routes apply the schema before dispatch, so missing top-level fields return `rejected` with `schema_invalid`.

## Aggregate entry points

```python
from glio_noncode import (
    default_validation_design_frontier_fixture,
    evaluate_validation_design_fixture,
    run_validation_design_runtime,
)

fixture = default_validation_design_frontier_fixture()
evaluation = evaluate_validation_design_fixture(fixture)
runtime = run_validation_design_runtime(fixture, run_id="local-review")
assert runtime.accepted
```

The runtime report exposes the core evaluation objects plus named assurance planes and ordered stage receipts.
