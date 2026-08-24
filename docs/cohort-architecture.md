# D12 Cohort Discovery and Longitudinal Aggregate

D12 is the twelfth deep product increment for `glio-noncode`. It joins four existing public aggregate cohort evidence families into one typed, deterministic, review-gated surface:

1. Foundation: cohort query, callable-space background rate, sequence context controls, and chromatin context controls.
2. Beta: regulatory recurrence, regional burden, functional convergence, and pathway or regulon convergence.
3. Alpha: clonality and timing, primary-to-recurrence comparison, treatment-selection signal detection, and cross-cohort replication.
4. Frontier: subgroup fairness stratification, transportability estimation, federated summaries, and cohort discovery publication.

The aggregate contains 22 source receipts, 16 ordered operations, and 64 cases. Every operation has one positive case and three controls. The controls retain the family’s real negative, incomplete, foreign-context, abstention, contradiction, parity, privacy, shift, and invalid-input paths. The evaluation emits 64 receipts and 392 checks.

## Scope and context

The envelope boundary is `public_aggregate_non_patient`. D12 deliberately retains four exact family context keys because cohort evidence is not automatically transportable across callable space, tumor territory, treatment phase, longitudinal phase, or study. The aggregate context is `multi_context_public_aggregate`; each source and case keeps its exact delegate context in `source_context_key` or `delegate_context_key`.

The fixture uses the existing public aggregate family values and delegated evaluators. It retains source identifiers, aggregate sample and feature fields already present in the family fixtures, issue codes, state values, output addresses, and declared limitations. It does not convert descriptive recurrence, convergence, fairness, transport, or discovery summaries into causal, prognostic, treatment, or clinical claims.

## Runtime closure

`run_cohort_architecture` executes 22 stages covering source audit, schema validation, dependency planning, four family joins, case execution, control routing, lineage, ledger, metrics, replay, artifacts, release, quality, depth, and observability. A release is published only when all delegate states and declared control paths match their receipts.

The six artifacts are the public fixture projection, data audit, evaluation receipts, review queue, event ledger, and release projection. Each artifact has a stable content address and public aggregate visibility.

## Python surface

```python
from glio_noncode import (
    assess_cohort_architecture_depth,
    cohort_architecture_depth_percent,
    default_cohort_architecture_fixture,
    evaluate_cohort_architecture_fixture,
    run_cohort_architecture,
)

fixture = default_cohort_architecture_fixture()
evaluation = evaluate_cohort_architecture_fixture(fixture)
runtime = run_cohort_architecture(fixture)
depth = assess_cohort_architecture_depth(fixture, evaluation)

assert runtime.accepted
assert cohort_architecture_depth_percent(depth) == 100.0
```
