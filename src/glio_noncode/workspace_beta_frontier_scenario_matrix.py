"""Scenario matrix for boundary and failure behavior across projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_public_data import BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierScenario:
    scenario_id: str
    operation: BetaFrontierOperation
    dimension: str
    input_state: str
    expected_state: str
    expected_issue: str | None
    expected_visibility: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("scenario_id", "dimension", "input_state", "expected_state", "expected_visibility", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierScenarioMatrix:
    version: str
    scenarios: tuple[BetaFrontierScenario, ...]
    dimensions: tuple[str, ...]
    content_address: str

    def by_operation(self, operation: BetaFrontierOperation) -> tuple[BetaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation is operation)

    def by_dimension(self, dimension: str) -> tuple[BetaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.dimension == dimension)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _scenario(index: int, operation: BetaFrontierOperation, dimension: str, input_state: str, expected_state: str, issue: str | None, visibility: str) -> BetaFrontierScenario:
    body = {"scenario_id": f"beta-scenario-{index:02d}", "operation": operation, "dimension": dimension, "input_state": input_state, "expected_state": expected_state, "expected_issue": issue, "expected_visibility": visibility}
    return BetaFrontierScenario(**body, content_address=content_hash(body))


def build_beta_frontier_scenario_matrix() -> BetaFrontierScenarioMatrix:
    scenarios: list[BetaFrontierScenario] = []
    index = 1
    dimensions = ("exact_context", "foreign_context", "missing_input", "contradiction", "pagination", "reconciliation", "empty_result", "bounded_output")
    states = {
        BetaFrontierOperation.TOPOLOGY_VIEWPORT: (("exact_context", "observed", "supported", None, "render"), ("foreign_context", "foreign", "out_of_domain", "context_mismatch", "withhold"), ("missing_input", "empty", "absent", "no_topology_observations", "show_empty"), ("contradiction", "ambiguous", "partial", "context_mismatch", "review"), ("pagination", "bounded", "supported", None, "render"), ("reconciliation", "unreconciled", "partial", "context_mismatch", "review"), ("empty_result", "none", "absent", "no_topology_observations", "show_empty"), ("bounded_output", "large", "supported", None, "truncate")),
        BetaFrontierOperation.CAUSAL_CHAIN: (("exact_context", "complete", "complete", None, "render"), ("foreign_context", "foreign", "out_of_domain", "context_mismatch", "withhold"), ("missing_input", "missing", "incomplete", "missing_mediator", "review"), ("contradiction", "against", "contradictory", "contradictory_mediator", "review"), ("pagination", "alternative", "complete", None, "retain"), ("reconciliation", "partial", "incomplete", "missing_mediator", "review"), ("empty_result", "none", "abstained", "missing_mediator", "show_empty"), ("bounded_output", "many_paths", "complete", None, "retain")),
        BetaFrontierOperation.POSTERIOR_DECOMPOSITION: (("exact_context", "reconciled", "supported", None, "render"), ("foreign_context", "foreign", "out_of_domain", "foreign_component", "withhold"), ("missing_input", "no_support", "abstained", "missing_support", "abstain"), ("contradiction", "ambiguous", "partial", "unreconciled_components", "review"), ("pagination", "many_components", "supported", None, "retain"), ("reconciliation", "residual", "partial", "unreconciled_components", "review"), ("empty_result", "none", "partial", "unreconciled_components", "show_residual"), ("bounded_output", "large", "supported", None, "truncate")),
        BetaFrontierOperation.EVIDENCE_TABLE: (("exact_context", "rows", "partial", None, "render"), ("foreign_context", "foreign", "out_of_domain", "context_mismatch", "withhold"), ("missing_input", "no_filter", "partial", None, "render"), ("contradiction", "partial_state", "partial", None, "review"), ("pagination", "offset", "partial", "pagination_applied", "retain_total"), ("reconciliation", "facets", "partial", None, "retain_facets"), ("empty_result", "no_rows", "absent", "no_matching_rows", "show_empty"), ("bounded_output", "many_rows", "partial", "pagination_applied", "truncate")),
    }
    for operation in BetaFrontierOperation:
        for row in states[operation]:
            scenarios.append(_scenario(index, operation, *row))
            index += 1
    body = {"version": "2026.08.d15.c05-c08.v1", "scenarios": tuple(scenarios), "dimensions": dimensions}
    return BetaFrontierScenarioMatrix(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierScenario", "BetaFrontierScenarioMatrix", "build_beta_frontier_scenario_matrix"]
