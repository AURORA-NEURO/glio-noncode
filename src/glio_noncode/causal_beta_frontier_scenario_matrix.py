"""Scenario matrix for C05-C08 positive and negative controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, CausalBetaFrontierOperation, default_causal_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierScenario:
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
class CausalBetaFrontierScenarioMatrix:
    fixture_id: str
    scenarios: tuple[CausalBetaFrontierScenario, ...]
    operation_count: int
    scenario_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def control_kinds(self) -> tuple[str, ...]:
        return tuple(sorted({item.control_kind for item in self.scenarios}))

    def for_operation(self, operation: str) -> tuple[CausalBetaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation == operation)

    def for_control(self, control_kind: str) -> tuple[CausalBetaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.control_kind == control_kind)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "scenarios": [item.to_dict() for item in self.scenarios], "operation_count": self.operation_count, "scenario_count": self.scenario_count, "control_kinds": self.control_kinds, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_scenario_matrix(fixture: CausalBetaFrontierFixture | None = None, evaluation: CausalBetaFrontierEvaluation | None = None) -> CausalBetaFrontierScenarioMatrix:
    value = fixture or default_causal_beta_frontier_fixture()
    scenarios: list[CausalBetaFrontierScenario] = []
    for operation in CausalBetaFrontierOperation:
        rows = value.operation_records(operation)
        groups = (
            ("positive", tuple(item for item in rows if item.role.value == "positive")),
            ("minimum_or_missing", tuple(item for item in rows if item.expected_state.value == "partial")),
            ("contradictory_or_ambiguous", tuple(item for item in rows if item.expected_state.value in {"contradictory", "ambiguous"})),
            ("foreign_context", tuple(item for item in rows if item.context_key == value.foreign_context_key)),
        )
        for control_kind, selected in groups:
            if not selected:
                continue
            selected_ids = {item.record_id for item in selected}
            observed = tuple(item.observed_state for item in (evaluation.rows if evaluation else ()) if item.record_id in selected_ids)
            expected = tuple(item.expected_state.value for item in selected)
            issues = tuple(sorted({issue for item in selected for issue in item.expected_issue_codes}))
            scenarios.append(CausalBetaFrontierScenario(f"{operation.value}:{control_kind}", operation.value, control_kind, tuple(item.record_id for item in selected), observed or expected, issues, f"exercise {control_kind} behavior for {operation.value}", not observed or observed == expected))
    values = tuple(scenarios)
    return CausalBetaFrontierScenarioMatrix(value.fixture_id, values, 4, len(values), bool(values) and len({item.operation for item in values}) == 4 and all(item.accepted for item in values))


__all__ = ["CausalBetaFrontierScenario", "CausalBetaFrontierScenarioMatrix", "build_causal_beta_frontier_scenario_matrix"]
