"""D12 cardinality, state, control, and receipt metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .cohort_architecture_contracts import (
    CohortArchitectureEvaluation,
    CohortArchitectureFixture,
)


def cohort_architecture_metrics(
    fixture: CohortArchitectureFixture,
    evaluation: CohortArchitectureEvaluation,
) -> dict[str, Any]:
    scenario_counts = Counter(item.scenario.value for item in fixture.cases)
    state_counts = Counter(item.observed_state.value for item in evaluation.executions)
    family_counts = Counter(item.family.value for item in fixture.cases)
    operation_counts = Counter(item.operation.value for item in fixture.cases)
    return {
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": scenario_counts["positive"],
        "control_count": sum(
            scenario_counts[item] for item in ("control_a", "control_b", "control_c")
        ),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "state_counts": dict(sorted(state_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "operation_counts": dict(sorted(operation_counts.items())),
        "receipt_count": len(evaluation.receipts),
        "check_count": len(evaluation.checks),
        "receipt_pass_rate": round(
            sum(item.passed for item in evaluation.receipts) / len(evaluation.receipts), 6
        )
        if evaluation.receipts
        else 0.0,
        "evaluation_accepted": evaluation.accepted,
    }


def cohort_architecture_metric_invariants(metrics: dict[str, Any]) -> tuple[str, ...]:
    failures = []
    for field, expected in (
        ("source_count", 22),
        ("operation_count", 16),
        ("case_count", 64),
        ("receipt_count", 64),
        ("check_count", 392),
    ):
        if metrics.get(field) != expected:
            failures.append(field)
    if metrics.get("receipt_pass_rate") != 1.0:
        failures.append("receipt_pass_rate")
    if metrics.get("scenario_counts") != {
        "control_a": 16,
        "control_b": 16,
        "control_c": 16,
        "positive": 16,
    }:
        failures.append("scenario_counts")
    return tuple(failures)


__all__ = ["cohort_architecture_metric_invariants", "cohort_architecture_metrics"]
