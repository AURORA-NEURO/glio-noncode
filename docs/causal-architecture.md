# D11 Causal Evidence Research Aggregate

D11 is the eleventh deep product increment for `glio-noncode`. It joins four existing public aggregate evidence families into one typed, deterministic, review-gated research surface:

1. Foundation: typed hypotheses, factor graphs, context-conditioned priors, and measurement likelihoods.
2. Beta: sequence-to-element, element-to-gene, gene-to-state, and counterfactual allele-state mediators.
3. Alpha: mediation sensitivity, confounding checklists, dependence correction, and negative evidence.
4. Frontier: posterior decomposition, regulatory-driver posterior, selective prediction abstention, and causal dossier publication.

The aggregate fixture contains 20 public source receipts, 16 ordered operations, and 64 cases. Every operation has one positive case plus three controls: `control_a`, `control_b`, and `control_c`. The positive set contains 16 cases and the control set contains 48 cases. The evaluation emits 64 case receipts and 392 checks.

## Scope

The release boundary is `public_aggregate_non_patient`. The pinned context is `GRCh38|glioma|adult|stem_like|core|unknown`; a differentiated-cell context is retained as an explicit foreign-context control. Source identifiers, delegate record identifiers, context tuples, issue codes, and content addresses are retained for reproducibility. Payloads remain bounded research summaries.

D11 does not claim causal identification, biological mechanism proof, clinical utility, treatment selection, or patient-specific inference. Posterior, driver, mediator, sensitivity, and dossier outputs are structured research proxies whose assumptions, dependence, missingness, and context boundaries remain visible.

## Runtime closure

`run_causal_architecture` executes a 22-stage runtime. The stages cover fixture loading, source audit, schema validation, dependency planning, four family joins, case execution, review routing, lineage, ledger, metrics, replay, artifact materialization, bundle closure, release, quality, depth, controls, and observability. A release is published only when the audit, plan, evaluation, review routing, replay, quality gate, and release checks all close.

The six artifact types are a public fixture projection, evaluation receipts, review queue, lineage projection, metrics projection, and release manifest. Each artifact records source addresses and a stable content address. The release manifest includes limitations and the public boundary.

## Python surface

```python
from glio_noncode import (
    assess_causal_architecture_depth,
    causal_architecture_depth_percent,
    default_causal_architecture_fixture,
    evaluate_causal_architecture_fixture,
    run_causal_architecture,
)

fixture = default_causal_architecture_fixture()
evaluation = evaluate_causal_architecture_fixture(fixture)
runtime = run_causal_architecture(fixture)
depth = assess_causal_architecture_depth(fixture, evaluation)

assert runtime.accepted
assert causal_architecture_depth_percent(depth) == 100.0
```

The aggregate export surface is intentionally explicit and deterministic. `causal_architecture_fixture_json` provides a stable JSON projection suitable for the checked-in public data file and replay tests.
