"""Capability-level validation matrix for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierEvaluation
from .causal_alpha_frontier_contracts import CausalAlphaFrontierContractReport
from .causal_alpha_frontier_metrics import CausalAlphaFrontierMetrics
from .causal_alpha_frontier_public_data import CausalAlphaFrontierOperation
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierValidationCell:
    capability_id: str
    operation: CausalAlphaFrontierOperation
    contract_id: str
    record_ids: tuple[str, ...]
    accepted_count: int
    expected_count: int
    release_state: str
    limitation: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"capability_id": self.capability_id, "operation": self.operation, "contract_id": self.contract_id, "record_ids": self.record_ids, "accepted_count": self.accepted_count, "expected_count": self.expected_count, "release_state": self.release_state, "limitation": self.limitation, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierValidationMatrix:
    fixture_id: str
    cells: tuple[CausalAlphaFrontierValidationCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> CausalAlphaFrontierValidationCell:
        return next(item for item in self.cells if item.capability_id == capability_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_validation_matrix(fixture_id: str, evaluation: CausalAlphaFrontierEvaluation, contracts: CausalAlphaFrontierContractReport, metrics: CausalAlphaFrontierMetrics) -> CausalAlphaFrontierValidationMatrix:
    cells: list[CausalAlphaFrontierValidationCell] = []
    capability_ids = ("GNC-D11-C09", "GNC-D11-C10", "GNC-D11-C11", "GNC-D11-C12")
    for capability_id, operation in zip(capability_ids, CausalAlphaFrontierOperation, strict=True):
        rows = evaluation.for_operation(operation) if hasattr(evaluation, "for_operation") else evaluation.evaluation.for_operation(operation)
        contract = contracts.for_capability(capability_id)
        metric = metrics.operation(operation)
        cells.append(CausalAlphaFrontierValidationCell(capability_id, operation, contract.contract_id, tuple(item.record_id for item in rows), sum(item.accepted for item in rows), len(rows), "verified" if all(item.accepted for item in rows) else "partial", contract.limitation, all(item.accepted for item in rows) and metric.record_count == 4))
    return CausalAlphaFrontierValidationMatrix(fixture_id, tuple(cells), len(cells) == 4 and all(item.accepted for item in cells))


__all__ = ["CausalAlphaFrontierValidationCell", "CausalAlphaFrontierValidationMatrix", "build_causal_alpha_frontier_validation_matrix"]
