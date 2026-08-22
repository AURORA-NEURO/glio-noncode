"""Scenario matrix for validation-planning boundary combinations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_public_data import ValidationFrontierOperation


@dataclass(frozen=True, slots=True)
class ValidationFrontierScenario:
    scenario_id: str
    operation: ValidationFrontierOperation
    context_match: bool
    inventory_match: bool
    insert_in_range: bool
    construct_budget: int
    expected_state: str
    expected_issue: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierScenarioMatrix:
    dimensions: tuple[str, ...]
    scenarios: tuple[ValidationFrontierScenario, ...]
    content_address: str

    @property
    def review_scenarios(self) -> tuple[ValidationFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.expected_state in {"blocked", "partial", "invalid"})

    @property
    def ready_scenarios(self) -> tuple[ValidationFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.expected_state in {"ready_for_review"})

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_frontier_scenario_matrix() -> ValidationFrontierScenarioMatrix:
    rows: list[ValidationFrontierScenario] = []
    for index in range(27):
        context_match = index % 3 != 1
        inventory_match = index % 4 != 1
        insert_in_range = index % 5 != 2
        budget = 4 if index % 2 else 2
        state = "ready_for_review" if context_match and inventory_match and insert_in_range else "blocked"
        issue = None if state == "ready_for_review" else ("context_mismatch" if not context_match else "model_system_not_available" if not inventory_match else "insert_length")
        operation = (ValidationFrontierOperation.MPRA_PLANNING if index % 2 == 0 else ValidationFrontierOperation.STARR_SEQ_PLANNING)
        body = {"scenario_id": f"design-{index + 1:03d}", "operation": operation, "context_match": context_match, "inventory_match": inventory_match, "insert_in_range": insert_in_range, "construct_budget": budget, "expected_state": state, "expected_issue": issue}
        rows.append(ValidationFrontierScenario(**body, content_address=content_hash(body)))
    for index, operation in enumerate(ValidationFrontierOperation, start=1):
        body = {"scenario_id": f"operation-{index:02d}", "operation": operation, "context_match": True, "inventory_match": True, "insert_in_range": True, "construct_budget": 4, "expected_state": "partial" if operation is ValidationFrontierOperation.EVIDENCE_GAP else "ready_for_review", "expected_issue": None}
        rows.append(ValidationFrontierScenario(**body, content_address=content_hash(body)))
    body = {"dimensions": ("operation", "context_match", "inventory_match", "insert_in_range", "construct_budget", "expected_state"), "scenarios": tuple(rows)}
    return ValidationFrontierScenarioMatrix(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierScenario", "ValidationFrontierScenarioMatrix", "build_validation_frontier_scenario_matrix"]
