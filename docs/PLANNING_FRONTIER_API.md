# Planning frontier API

Core contracts live in `planning_frontier_contracts.py`:

- `PlanningOperation` closes the four operations.
- `PlanningState` distinguishes ready, review, blocked, rejected, and abstained.
- `PlanningFixture` binds public source receipts to scenario records.
- `PlanningOperationResult` carries state, issue codes, output, and address.
- `PlanningEvaluation` carries five checks per scenario.

Functional entry points live in `planning_frontier_operations.py`:

```python
evaluate_model_system_eligibility(payload)
evaluate_guide_oligo_adaptation(payload)
evaluate_controls_randomization(payload)
evaluate_power_replication(payload)
run_planning_operation(operation, payload)
```

Use `default_planning_frontier_fixture()` for the reproducible public aggregate
fixture and `run_planning_runtime()` for the complete staged rehearsal.
