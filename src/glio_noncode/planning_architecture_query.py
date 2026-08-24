"""Deterministic safe query surface for D13 cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_architecture_contracts import (
    PlanningArchitectureCase,
    PlanningArchitectureFamily,
    PlanningArchitectureFixture,
    PlanningArchitectureOperation,
    PlanningArchitectureScenario,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture


@dataclass(frozen=True, slots=True)
class PlanningArchitectureQueryResult:
    fixture_id: str
    filters: dict[str, str | None]
    cases: tuple[dict[str, Any], ...]
    count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "filters": self.filters,
            "cases": list(self.cases),
            "count": self.count,
            "content_address": self.content_address,
        }


def _case_view(case: PlanningArchitectureCase, include_payload: bool) -> dict[str, Any]:
    return case.to_dict(include_payload=include_payload)


def query_planning_architecture(
    fixture: PlanningArchitectureFixture | None = None,
    *,
    operation_id: str | None = None,
    family: str | PlanningArchitectureFamily | None = None,
    scenario: str | PlanningArchitectureScenario | None = None,
    include_payload: bool = False,
) -> PlanningArchitectureQueryResult:
    selected = fixture or default_planning_architecture_fixture()
    family_value = family.value if isinstance(family, PlanningArchitectureFamily) else family
    scenario_value = (
        scenario.value if isinstance(scenario, PlanningArchitectureScenario) else scenario
    )
    operation_value = (
        operation_id.value
        if isinstance(operation_id, PlanningArchitectureOperation)
        else operation_id
    )
    cases = tuple(
        case
        for case in selected.cases
        if (operation_value is None or case.operation_id == operation_value)
        and (family_value is None or case.family.value == family_value)
        and (scenario_value is None or case.scenario.value == scenario_value)
    )
    projections = tuple(_case_view(case, include_payload) for case in cases)
    filters = {
        "operation_id": operation_value,
        "family": family_value,
        "scenario": scenario_value,
        "include_payload": str(include_payload).lower(),
    }
    body = {"fixture_id": selected.fixture_id, "filters": filters, "cases": projections}
    return PlanningArchitectureQueryResult(
        selected.fixture_id,
        filters,
        projections,
        len(projections),
        addressed(body, "planning-query"),
    )


def query_planning_architecture_cases(
    fixture: PlanningArchitectureFixture | None = None,
    **filters: Any,
) -> tuple[dict[str, Any], ...]:
    return query_planning_architecture(fixture, **filters).cases


__all__ = [
    "PlanningArchitectureQueryResult",
    "query_planning_architecture",
    "query_planning_architecture_cases",
]
