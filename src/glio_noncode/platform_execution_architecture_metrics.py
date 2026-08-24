"""D16 state, operation, family, scenario, and issue metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .platform_execution_architecture_contracts import (
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    addressed,
)
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def platform_execution_metrics(
    fixture: PlatformExecutionFixture | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
) -> dict[str, Any]:
    selected = fixture or default_platform_execution_fixture()
    if evaluation is None:
        from .platform_execution_architecture_operations import evaluate_platform_execution_fixture

        evaluation = evaluate_platform_execution_fixture(selected)
    states = Counter(item.observed_state.value for item in evaluation.executions)
    families = Counter(item.family.value for item in evaluation.executions)
    operations = Counter(item.operation.value for item in evaluation.executions)
    scenarios = Counter(item.scenario.value for item in evaluation.executions)
    issues = Counter(issue for item in evaluation.executions for issue in item.observed_issue_codes)
    body = {
        "fixture_id": selected.fixture_id,
        "source_count": len(selected.sources),
        "operation_count": len(selected.operations),
        "case_count": len(selected.cases),
        "positive_count": len(selected.positive_cases),
        "control_count": len(selected.control_cases),
        "state_counts": dict(sorted(states.items())),
        "family_counts": dict(sorted(families.items())),
        "operation_counts": dict(sorted(operations.items())),
        "scenario_counts": dict(sorted(scenarios.items())),
        "issue_counts": dict(sorted(issues.items())),
        "check_count": len(evaluation.checks),
        "accepted": evaluation.accepted,
    }
    return body | {"content_address": addressed(body, "platform-execution-metrics")}


def platform_execution_metric_invariants(metrics: dict[str, Any]) -> tuple[str, ...]:
    failures = []
    for name, required in (
        ("source_count", 19),
        ("operation_count", 16),
        ("case_count", 64),
        ("positive_count", 16),
        ("control_count", 48),
    ):
        if metrics.get(name) != required:
            failures.append(name)
    if any(value != 4 for value in metrics.get("operation_counts", {}).values()):
        failures.append("operation_balance")
    if metrics.get("family_counts") != {
        "platform_frontier": 16,
        "control_frontier": 32,
        "deployment_frontier": 16,
    }:
        failures.append("family_balance")
    if any(value != 16 for value in metrics.get("scenario_counts", {}).values()):
        failures.append("scenario_balance")
    return tuple(failures)


__all__ = ["platform_execution_metric_invariants", "platform_execution_metrics"]
