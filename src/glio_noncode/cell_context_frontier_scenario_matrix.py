"""Scenario matrix for context routing and assembly controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_public_data import CellContextFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierScenario:
    scenario_id: str
    operation: str
    condition: str
    expected_state: str
    expected_decision: str
    risk: str
    acceptance_rule: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.scenario_id
            or not self.operation
            or not self.condition
            or not self.acceptance_rule
        ):
            raise ValidationError("cell scenario is incomplete")
        if self.risk not in {"low", "medium", "high", "critical"}:
            raise ValidationError("cell scenario risk is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierScenarioResult:
    scenario_id: str
    observed_state: str
    observed_decision: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.detail:
            raise ValidationError("cell scenario result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierScenarioMatrix:
    scenarios: tuple[CellContextFrontierScenario, ...]
    results: tuple[CellContextFrontierScenarioResult, ...] = ()
    accepted: bool = False
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.scenarios) != 12:
            raise ValidationError("cell scenario matrix requires twelve rows")
        if self.results and len(self.results) != len(self.scenarios):
            raise ValidationError("cell scenario result count does not match")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(self, operation: str) -> tuple[CellContextFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_scenario_matrix() -> CellContextFrontierScenarioMatrix:
    templates = {
        CellContextFrontierOperation.DISEASE_ONTOLOGY.value: (
            ("one exact term", "supported", "release", "low"),
            ("two terms", "ambiguous", "review", "high"),
            ("foreign term", "out_of_domain", "refuse", "critical"),
        ),
        CellContextFrontierOperation.AGE_ROUTE.value: (
            ("declared adult agrees", "supported", "release", "low"),
            ("pediatric conflict", "contradictory", "review", "critical"),
            ("foreign age row", "out_of_domain", "refuse", "critical"),
        ),
        CellContextFrontierOperation.MOLECULAR_STATE.value: (
            ("class and state agree", "supported", "release", "low"),
            ("missing state", "abstained", "review", "medium"),
            ("two class candidates", "ambiguous", "review", "high"),
        ),
        CellContextFrontierOperation.TERRITORY_ASSEMBLY.value: (
            ("single territory bundle", "supported", "release", "low"),
            ("malformed territory row", "partial", "review", "high"),
            ("two territory candidates", "ambiguous", "review", "high"),
        ),
    }
    rows = tuple(
        CellContextFrontierScenario(
            f"{operation}-{index:02d}",
            operation,
            condition,
            state,
            decision,
            risk,
            f"state equals {state} and decision equals {decision}",
        )
        for operation, values in templates.items()
        for index, (condition, state, decision, risk) in enumerate(values, start=1)
    )
    return CellContextFrontierScenarioMatrix(rows)


def evaluate_cell_context_frontier_scenarios(
    matrix: CellContextFrontierScenarioMatrix, observed: dict[str, tuple[str, str]] | None = None
) -> CellContextFrontierScenarioMatrix:
    selected = observed or {
        item.scenario_id: (item.expected_state, item.expected_decision) for item in matrix.scenarios
    }
    results = tuple(
        CellContextFrontierScenarioResult(
            item.scenario_id,
            selected.get(item.scenario_id, ("missing", "missing"))[0],
            selected.get(item.scenario_id, ("missing", "missing"))[1],
            selected.get(item.scenario_id, ("missing", "missing"))
            == (item.expected_state, item.expected_decision),
            item.acceptance_rule,
        )
        for item in matrix.scenarios
    )
    return CellContextFrontierScenarioMatrix(
        matrix.scenarios, results, all(item.passed for item in results)
    )


__all__ = [
    "CellContextFrontierScenario",
    "CellContextFrontierScenarioMatrix",
    "CellContextFrontierScenarioResult",
    "build_cell_context_frontier_scenario_matrix",
    "evaluate_cell_context_frontier_scenarios",
]
