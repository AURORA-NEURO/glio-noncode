"""Scenario matrix for positive, missing, contradictory, and foreign rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture, CausalFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierScenario:
    scenario_id: str
    operation: str
    control_kind: str
    record_ids: tuple[str, ...]
    expected_states: tuple[str, ...]
    expected_issue_codes: tuple[str, ...]
    purpose: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"scenario_id": self.scenario_id, "operation": self.operation, "control_kind": self.control_kind, "record_ids": self.record_ids, "expected_states": self.expected_states, "expected_issue_codes": self.expected_issue_codes, "purpose": self.purpose, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierScenarioMatrix:
    fixture_id: str
    scenarios: tuple[CausalFoundationFrontierScenario, ...]
    operation_count: int
    scenario_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[CausalFoundationFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation == operation)

    def for_control(self, control_kind: str) -> tuple[CausalFoundationFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.control_kind == control_kind)

    @property
    def control_kinds(self) -> tuple[str, ...]:
        return tuple(sorted({item.control_kind for item in self.scenarios}))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "scenarios": [item.to_dict() for item in self.scenarios], "operation_count": self.operation_count, "scenario_count": self.scenario_count, "control_kinds": self.control_kinds, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_foundation_frontier_scenario_matrix(fixture: CausalFoundationFrontierFixture | None = None, evaluation: CausalFoundationFrontierEvaluation | None = None) -> CausalFoundationFrontierScenarioMatrix:
    value = fixture or __import__("glio_noncode.causal_foundation_frontier_public_data", fromlist=["default_causal_foundation_frontier_fixture"]).default_causal_foundation_frontier_fixture()
    rows = evaluation.rows if evaluation is not None else ()
    scenarios: list[CausalFoundationFrontierScenario] = []
    for operation in CausalFoundationFrontierOperation:
        op_records = value.operation_records(operation)
        for control_kind, selected in (("positive", tuple(item for item in op_records if item.role.value == "positive")), ("missing", tuple(item for item in op_records if "missing" in item.description or "single" in item.description)), ("contradictory", tuple(item for item in op_records if "contradictory" in item.description)), ("foreign_context", tuple(item for item in op_records if item.context_key == value.foreign_context_key))):
            if not selected:
                continue
            scenario_id = f"{operation.value}:{control_kind}"
            observed = tuple(item.observed_state for item in rows if item.record_id in {record.record_id for record in selected})
            expected = tuple(item.expected_state.value for item in selected)
            issues = tuple(sorted({issue for item in selected for issue in item.expected_issue_codes}))
            scenarios.append(CausalFoundationFrontierScenario(scenario_id, operation.value, control_kind, tuple(item.record_id for item in selected), observed or expected, issues, f"exercise {control_kind} behavior for {operation.value}", not observed or observed == expected))
    values = tuple(scenarios)
    return CausalFoundationFrontierScenarioMatrix(value.fixture_id, values, len(tuple(CausalFoundationFrontierOperation)), len(values), bool(values) and len({item.operation for item in values}) == 4 and all(item.accepted for item in values))


__all__ = ["CausalFoundationFrontierScenario", "CausalFoundationFrontierScenarioMatrix", "build_causal_foundation_frontier_scenario_matrix"]
