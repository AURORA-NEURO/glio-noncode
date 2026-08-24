"""Control-case projections and balance checks for D15."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .workbench_architecture_contracts import (
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureScenario,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def workbench_architecture_control_rows(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_workbench_architecture_fixture()
    rows = []
    for case in selected.control_cases:
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family,
            "plane": case.plane,
            "scenario": case.scenario,
            "expected_state": case.expected_state,
            "expected_issue_codes": case.expected_issue_codes,
            "delegate_context_key": case.delegate_context_key,
            "description": case.description,
        }
        rows.append(body | {"content_address": addressed(body, "workbench-architecture-control")})
    return tuple(rows)


def workbench_architecture_control_summary(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> dict[str, object]:
    selected = fixture or default_workbench_architecture_fixture()
    counts = Counter(item.scenario.value for item in selected.cases)
    states = Counter(item.expected_state.value for item in selected.control_cases)
    return {
        "fixture_id": selected.fixture_id,
        "positive_count": counts[WorkbenchArchitectureScenario.POSITIVE.value],
        "control_count": len(selected.control_cases),
        "scenario_counts": dict(sorted(counts.items())),
        "control_state_counts": dict(sorted(states.items())),
        "balanced": counts == Counter({item.value: 16 for item in WorkbenchArchitectureScenario}),
        "control_address_count": len(workbench_architecture_control_rows(selected)),
    }


__all__ = ["workbench_architecture_control_rows", "workbench_architecture_control_summary"]
