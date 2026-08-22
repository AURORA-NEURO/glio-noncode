# Workspace beta frontier evidence gate

The gate evaluates a projection package in layers. A release is accepted only
when every blocking check passes.

## Blocking checks

- all positive fixture paths match expected state and issues
- control paths remain distinct from positive acceptance
- four operation contracts are registered
- four operation schemas are registered
- issue values fit the operation contract
- state values fit the operation contract
- execution receipts are content addressed
- the fixture boundary is public aggregate data
- the source-to-output lineage graph is acyclic
- expected and observed rows reconcile
- the runtime includes all eight stages
- replay produces the same evaluation and execution addresses

## Advisory checks

Advisory checks make depth visible without blocking a valid research package:

- partial topology or table state is represented
- contradictory chain state is represented
- empty output is represented
- pagination retains its total match count
- posterior residual is present
- source versions survive projection rendering

## Acceptance rule

```python
accepted = (
    evaluation.accepted
    and reconciliation.reconciled
    and quality.accepted
    and bundle.accepted
)
```

No gate converts an unresolved state to a negative state. No gate removes
foreign-context rows from the audit trail. No gate treats a descriptive
posterior proxy as a clinical probability.

## Control matrix

Each surface has three controls:

| Surface | Controls |
| --- | --- |
| topology | foreign context, invalid focus, empty observations |
| causal | foreign context, missing mediator, contradiction |
| posterior | foreign component, unreconciled contribution, missing support |
| table | foreign context, no matching dimension, paginated page |

This matrix provides a minimum contract for future UI and API clients. A
client may render richer controls, but it must preserve these state and issue
boundaries.
