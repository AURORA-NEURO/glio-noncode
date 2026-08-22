"""Scenario matrix for happy paths, controls, and boundary transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_public_data import ChromatinContextFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierScenario:
    scenario_id: str
    operation: str
    input_condition: str
    expected_state: str
    expected_decision: str
    risk: str
    acceptance_rule: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.operation or not self.input_condition:
            raise ValidationError("scenario is incomplete")
        if self.risk not in {"low", "medium", "high", "critical"}:
            raise ValidationError("scenario risk is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierScenarioResult:
    scenario_id: str
    observed_state: str
    observed_decision: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.detail:
            raise ValidationError("scenario result is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierScenarioMatrix:
    scenarios: tuple[ChromatinContextFrontierScenario, ...]
    results: tuple[ChromatinContextFrontierScenarioResult, ...] = ()
    accepted: bool = False
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.scenarios) != 12:
            raise ValidationError("scenario matrix requires twelve scenarios")
        if self.results and len(self.results) != len(self.scenarios):
            raise ValidationError("scenario result count must match scenario count")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(self, operation: str) -> tuple[ChromatinContextFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_scenario_matrix() -> ChromatinContextFrontierScenarioMatrix:
    rows: list[ChromatinContextFrontierScenario] = []
    templates = {
        ChromatinContextFrontierOperation.TRACK_RETRIEVAL.value: (
            ("exact single interval", "supported", "release", "low"),
            ("malformed row beside valid interval", "partial", "review", "high"),
            ("two same-context replicates", "ambiguous", "review", "high"),
        ),
        ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA.value: (
            ("nonzero reference and alternate", "supported", "release", "low"),
            ("missing alternate signal", "abstained", "review", "medium"),
            ("foreign context measurement", "out_of_domain", "refuse", "critical"),
        ),
        ChromatinContextFrontierOperation.HISTONE_CONTEXT.value: (
            ("exact histone mark interval", "supported", "release", "low"),
            ("replicate spread", "ambiguous", "review", "high"),
            ("foreign context overlap", "out_of_domain", "refuse", "critical"),
        ),
        ChromatinContextFrontierOperation.H3K27AC_ACTIVITY.value: (
            ("exact H3K27ac interval", "supported", "release", "low"),
            ("no H3K27ac measurement", "abstained", "review", "medium"),
            ("foreign context H3K27ac", "out_of_domain", "refuse", "critical"),
        ),
    }
    for operation, items in templates.items():
        for index, (condition, state, decision, risk) in enumerate(items, start=1):
            rows.append(
                ChromatinContextFrontierScenario(
                    f"{operation}-{index:02d}",
                    operation,
                    condition,
                    state,
                    decision,
                    risk,
                    f"observed state equals {state} and decision equals {decision}",
                )
            )
    return ChromatinContextFrontierScenarioMatrix(tuple(rows))


def evaluate_chromatin_context_frontier_scenarios(
    matrix: ChromatinContextFrontierScenarioMatrix,
    observed: dict[str, tuple[str, str]] | None = None,
) -> ChromatinContextFrontierScenarioMatrix:
    selected = observed or {
        item.scenario_id: (item.expected_state, item.expected_decision) for item in matrix.scenarios
    }
    results = tuple(
        ChromatinContextFrontierScenarioResult(
            item.scenario_id,
            selected.get(item.scenario_id, ("missing", "missing"))[0],
            selected.get(item.scenario_id, ("missing", "missing"))[1],
            selected.get(item.scenario_id, ("missing", "missing"))
            == (item.expected_state, item.expected_decision),
            item.acceptance_rule,
        )
        for item in matrix.scenarios
    )
    return ChromatinContextFrontierScenarioMatrix(
        matrix.scenarios, results, all(item.passed for item in results)
    )


__all__ = [
    "ChromatinContextFrontierScenario",
    "ChromatinContextFrontierScenarioMatrix",
    "ChromatinContextFrontierScenarioResult",
    "build_chromatin_context_frontier_scenario_matrix",
    "evaluate_chromatin_context_frontier_scenarios",
]
