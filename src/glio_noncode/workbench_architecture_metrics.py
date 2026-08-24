"""State, scenario, family, operation, and issue metrics for D15."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .workbench_architecture_contracts import (
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def workbench_architecture_metrics(
    fixture: WorkbenchArchitectureFixture | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
) -> dict[str, Any]:
    selected = fixture or default_workbench_architecture_fixture()
    if evaluation is None:
        from .workbench_architecture_operations import evaluate_workbench_architecture_fixture

        evaluation = evaluate_workbench_architecture_fixture(selected)
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
    return body | {"content_address": addressed(body, "workbench-architecture-metrics")}


def workbench_architecture_metric_invariants(metrics: dict[str, Any]) -> tuple[str, ...]:
    failures = []
    for name, required in (
        ("source_count", 20),
        ("operation_count", 16),
        ("case_count", 64),
        ("positive_count", 16),
        ("control_count", 48),
    ):
        if metrics.get(name) != required:
            failures.append(name)
    if any(value != 4 for value in metrics.get("operation_counts", {}).values()):
        failures.append("operation_balance")
    if any(value != 16 for value in metrics.get("family_counts", {}).values()):
        failures.append("family_balance")
    if any(value != 16 for value in metrics.get("scenario_counts", {}).values()):
        failures.append("scenario_balance")
    return tuple(failures)


def workbench_architecture_metric_table(metrics: dict[str, Any]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "metric": name,
            "value": metrics.get(name),
            "address": addressed(
                {"metric": name, "value": metrics.get(name)}, "workbench-architecture-metric"
            ),
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
    "workbench_architecture_metric_invariants",
    "workbench_architecture_metric_table",
    "workbench_architecture_metrics",
]
