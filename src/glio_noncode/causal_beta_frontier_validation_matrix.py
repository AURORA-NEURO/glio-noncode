"""Capability-by-control validation matrix for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, CausalBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierMatrixCell:
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
class CausalBetaFrontierValidationMatrix:
    fixture_id: str
    dimensions: tuple[str, ...]
    cells: tuple[CausalBetaFrontierMatrixCell, ...]
    passed_count: int
    cell_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_cells(self) -> tuple[CausalBetaFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if not item.passed)

    def for_capability(self, capability_id: str) -> tuple[CausalBetaFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if item.capability_id == capability_id)

    def for_scenario(self, scenario: str) -> tuple[CausalBetaFrontierMatrixCell, ...]:
        return tuple(item for item in self.cells if item.scenario == scenario)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "dimensions": self.dimensions, "cells": [item.to_dict() for item in self.cells], "passed_count": self.passed_count, "cell_count": self.cell_count, "failed_cells": [item.record_id for item in self.failed_cells], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_validation_matrix(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation) -> CausalBetaFrontierValidationMatrix:
    capability_ids = {CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT.value: "GNC-D11-C05", CausalBetaFrontierOperation.ELEMENT_TO_GENE.value: "GNC-D11-C06", CausalBetaFrontierOperation.GENE_TO_STATE.value: "GNC-D11-C07", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE.value: "GNC-D11-C08"}
    cells: list[CausalBetaFrontierMatrixCell] = []
    for row in evaluation.rows:
        record = fixture.record_map()[row.record_id]
        if record.role.value == "positive":
            scenario = "positive"
        elif record.context_key == fixture.foreign_context_key:
            scenario = "foreign_context"
        elif row.observed_state in {"contradictory", "ambiguous"}:
            scenario = "conflict_or_ambiguity"
        else:
            scenario = "minimum_or_missing"
        cells.append(CausalBetaFrontierMatrixCell(capability_ids[row.operation], row.operation, scenario, row.record_id, row.expected_state, row.observed_state, row.observed_issue_codes, row.state_match and row.issue_match))
    values = tuple(cells)
    return CausalBetaFrontierValidationMatrix(fixture.fixture_id, ("capability", "operation", "scenario", "record"), values, sum(item.passed for item in values), len(values), bool(values) and all(item.passed for item in values))


__all__ = ["CausalBetaFrontierMatrixCell", "CausalBetaFrontierValidationMatrix", "build_causal_beta_frontier_validation_matrix"]
