"""Scenario coverage matrix for the eight lifecycle beta operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierOperation, LifecycleBetaFrontierRole
from .serialization import content_hash, jsonable


LIFECYCLE_BETA_FRONTIER_SCENARIO_AXES = ("positive", "context_boundary", "missing_or_empty", "contradiction_or_change")


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierScenarioCell:
    cell_id: str
    operation: LifecycleBetaFrontierOperation
    axis: str
    record_ids: tuple[str, ...]
    expected_states: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierScenarioMatrix:
    fixture_id: str
    axes: tuple[str, ...]
    cells: tuple[LifecycleBetaFrontierScenarioCell, ...]
    accepted: bool
    failed_cell_ids: tuple[str, ...]
    content_address: str

    def by_operation(self, operation: LifecycleBetaFrontierOperation | str) -> tuple[LifecycleBetaFrontierScenarioCell, ...]:
        selected = operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
        return tuple(item for item in self.cells if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_lifecycle_beta_frontier_scenarios(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierScenarioMatrix:
    cells = []
    for operation in LifecycleBetaFrontierOperation:
        rows = evaluation.by_operation(operation)
        grouped = (
            ("positive", tuple(item for item in rows if item.role is LifecycleBetaFrontierRole.POSITIVE)),
            ("context_boundary", tuple(item for item in rows if any(code in item.issue_codes for code in ("context_mismatch", "context_changed", "gate_context_mismatch")))),
            ("missing_or_empty", tuple(item for item in rows if any(code in item.issue_codes for code in ("no_claims", "no_entries", "no_active_claims", "no_review_items", "required_decision_count", "unclassified_tier", "missing_parent", "invalid_uncertainty", "blocking_gate")) or str(item.output.get("kind")) in {"stable", "empty"})),
            ("contradiction_or_change", tuple(item for item in rows if any(code in item.issue_codes for code in ("tier_direction_conflict", "contradictory_claim", "split_verdict", "claim_changed", "claim_added", "citation_changed", "duplicate_log_id", "explicit_rejection")) or str(item.output.get("kind")) in {"missing_parent", "invalid"})),
        )
        for axis, selected in grouped:
            body = {"cell_id": f"{operation.value}:{axis}", "operation": operation, "axis": axis, "record_ids": tuple(item.record_id for item in selected), "expected_states": tuple(item.state.value for item in selected), "accepted": bool(selected)}
            cells.append(LifecycleBetaFrontierScenarioCell(**body, content_address=content_hash(body)))
    failed = tuple(item.cell_id for item in cells if not item.accepted)
    return LifecycleBetaFrontierScenarioMatrix(evaluation.fixture_id, LIFECYCLE_BETA_FRONTIER_SCENARIO_AXES, tuple(cells), not failed, failed, content_hash({"cells": tuple(cells), "failed": failed}))


def validate_lifecycle_beta_frontier_scenarios(matrix: LifecycleBetaFrontierScenarioMatrix) -> bool:
    return matrix.accepted and len(matrix.cells) == 32 and all(tuple(matrix.by_operation(item.operation)) for item in matrix.cells)


__all__ = ["LIFECYCLE_BETA_FRONTIER_SCENARIO_AXES", "LifecycleBetaFrontierScenarioCell", "LifecycleBetaFrontierScenarioMatrix", "evaluate_lifecycle_beta_frontier_scenarios", "validate_lifecycle_beta_frontier_scenarios"]
