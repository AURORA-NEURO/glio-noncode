"""Capability-by-scenario validation matrix for the four causal foundations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture, CausalFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierMatrixCell:
    capability_id: str
    operation: str
    scenario: str
    record_id: str
    expected_state: str
    observed_state: str
    issue_codes: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierValidationMatrix:
    fixture_id: str
    dimensions: tuple[str, ...]
    cells: tuple[CausalFoundationFrontierMatrixCell, ...]
    passed_count: int
    cell_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_cells(self) -> tuple[CausalFoundationFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if not item.passed)

    def for_capability(self, capability_id: str) -> tuple[CausalFoundationFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if item.capability_id == capability_id)

    def for_scenario(self, scenario: str) -> tuple[CausalFoundationFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if item.scenario == scenario)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "dimensions": self.dimensions, "cells": [item.to_dict() for item in self.cells], "passed_count": self.passed_count, "cell_count": self.cell_count, "failed_cells": [item.record_id for item in self.failed_cells], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_foundation_frontier_validation_matrix(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation) -> CausalFoundationFrontierValidationMatrix:
    capability_ids = {CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT.value: "GNC-D11-C01", CausalFoundationFrontierOperation.FACTOR_GRAPH.value: "GNC-D11-C02", CausalFoundationFrontierOperation.CONTEXT_PRIOR.value: "GNC-D11-C03", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD.value: "GNC-D11-C04"}
    cells: list[CausalFoundationFrontierMatrixCell] = []
    for row in evaluation.rows:
        record = fixture.record_map()[row.record_id]
        scenario = "positive" if record.role.value == "positive" else ("foreign_context" if record.context_key == fixture.foreign_context_key else ("contradictory" if row.observed_state == "contradictory" else "missing_or_partial"))
        cells.append(CausalFoundationFrontierMatrixCell(capability_ids[row.operation], row.operation, scenario, row.record_id, row.expected_state, row.observed_state, row.observed_issue_codes, row.state_match and row.issue_match))
    values = tuple(cells)
    return CausalFoundationFrontierValidationMatrix(fixture.fixture_id, ("capability", "operation", "scenario", "record"), values, sum(item.passed for item in values), len(values), bool(values) and all(item.passed for item in values))


__all__ = ["CausalFoundationFrontierMatrixCell", "CausalFoundationFrontierValidationMatrix", "build_causal_foundation_frontier_validation_matrix"]
