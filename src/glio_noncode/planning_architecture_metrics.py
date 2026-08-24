"""D13 state, scenario, family, operation, and issue metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .planning_architecture_contracts import (
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture


def planning_architecture_metrics(
    fixture: PlanningArchitectureFixture | None = None,
    evaluation: PlanningArchitectureEvaluation | None = None,
) -> dict[str, Any]:
    selected = fixture or default_planning_architecture_fixture()
    if evaluation is None:
        from .planning_architecture_operations import evaluate_planning_architecture_fixture

        evaluation = evaluate_planning_architecture_fixture(selected)
    state_counts = Counter(item.observed_state.value for item in evaluation.executions)
    family_counts = Counter(item.family.value for item in evaluation.executions)
    operation_counts = Counter(item.operation.value for item in evaluation.executions)
    scenario_counts = Counter(item.scenario.value for item in evaluation.executions)
    issue_counts = Counter(
        issue for item in evaluation.executions for issue in item.observed_issue_codes
    )
    body = {
        "fixture_id": selected.fixture_id,
        "source_count": len(selected.sources),
        "operation_count": len(selected.operations),
        "case_count": len(selected.cases),
        "positive_count": len(selected.positive_cases),
        "control_count": len(selected.control_cases),
        "state_counts": dict(sorted(state_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "operation_counts": dict(sorted(operation_counts.items())),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "check_count": len(evaluation.checks),
        "accepted": evaluation.accepted,
    }
    return body | {"content_address": addressed(body, "planning-metrics")}


def planning_architecture_metric_invariants(metrics: dict[str, Any]) -> tuple[str, ...]:
    failures: list[str] = []
    if metrics.get("source_count") != 20:
        failures.append("source_count")
    if metrics.get("operation_count") != 16:
        failures.append("operation_count")
    if metrics.get("case_count") != 64:
        failures.append("case_count")
    if metrics.get("positive_count") != 16:
        failures.append("positive_count")
    if metrics.get("control_count") != 48:
        failures.append("control_count")
    if any(value != 4 for value in metrics.get("operation_counts", {}).values()):
        failures.append("operation_balance")
    if any(value != 16 for value in metrics.get("family_counts", {}).values()):
        failures.append("family_balance")
    if any(value != 16 for value in metrics.get("scenario_counts", {}).values()):
        failures.append("scenario_balance")
    return tuple(failures)


def planning_architecture_metric_table(metrics: dict[str, Any]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "metric": name,
            "value": metrics.get(name),
            "address": addressed({"metric": name, "value": metrics.get(name)}, "planning-metric"),
        }
        for name in (
            "source_count",
            "operation_count",
            "case_count",
            "positive_count",
            "control_count",
            "check_count",
            "accepted",
        )
    )


__all__ = [
    "planning_architecture_metric_invariants",
    "planning_architecture_metric_table",
    "planning_architecture_metrics",
]
