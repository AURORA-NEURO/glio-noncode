"""Balanced positive and negative controls for the D13 aggregate."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .planning_architecture_contracts import (
    PlanningArchitectureFixture,
    PlanningArchitectureScenario,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture


def planning_architecture_control_matrix(
    fixture: PlanningArchitectureFixture | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_planning_architecture_fixture()
    rows: list[dict[str, Any]] = []
    for operation in selected.operations:
        cases = [item for item in selected.cases if item.operation_id == operation.operation_id]
        for case in cases:
            body = {
                "operation_id": operation.operation_id,
                "case_id": case.case_id,
                "family": case.family,
                "scenario": case.scenario,
                "expected_state": case.expected_state,
                "expected_issue_codes": case.expected_issue_codes,
                "context_key": case.delegate_context_key,
                "is_control": case.scenario is not PlanningArchitectureScenario.POSITIVE,
            }
            rows.append(body | {"content_address": addressed(body, "planning-control-row")})
    return tuple(rows)


def planning_architecture_control_summary(
    fixture: PlanningArchitectureFixture | None = None,
) -> dict[str, Any]:
    selected = fixture or default_planning_architecture_fixture()
    rows = planning_architecture_control_matrix(selected)
    scenario_counts = Counter(item["scenario"].value for item in rows)
    issue_counts = Counter(issue for item in rows for issue in item["expected_issue_codes"])
    context_mismatch_count = sum(
        "context_mismatch" in item["expected_issue_codes"] for item in rows
    )
    return {
        "fixture_id": selected.fixture_id,
        "row_count": len(rows),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "context_mismatch_count": context_mismatch_count,
        "positive_count": scenario_counts["positive"],
        "control_count": sum(
            scenario_counts[item] for item in ("control_a", "control_b", "control_c")
        ),
        "balanced": all(
            scenario_counts[item] == 16
            for item in ("positive", "control_a", "control_b", "control_c")
        ),
    }


def planning_architecture_controls_are_balanced(
    fixture: PlanningArchitectureFixture | None = None,
) -> bool:
    return bool(planning_architecture_control_summary(fixture)["balanced"])


__all__ = [
    "planning_architecture_control_matrix",
    "planning_architecture_control_summary",
    "planning_architecture_controls_are_balanced",
]
