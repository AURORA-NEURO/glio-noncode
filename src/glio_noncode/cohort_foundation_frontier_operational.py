"""Operational disposition matrix for runtime and review consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_policy import CohortFoundationDisposition, CohortFoundationPolicy
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationOperationalCell:
    operation: CohortFoundationOperation
    state: str
    disposition: CohortFoundationDisposition
    consumer: str
    allowed: bool
    action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationOperationalMatrix:
    matrix_id: str
    cells: tuple[CohortFoundationOperationalCell, ...]
    accepted: bool
    content_address: str

    def for_operation(self, operation: CohortFoundationOperation) -> tuple[CohortFoundationOperationalCell, ...]:
        return tuple(item for item in self.cells if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_operational_matrix(policy: CohortFoundationPolicy) -> CohortFoundationOperationalMatrix:
    cells = []
    for decision in policy.decisions:
        consumer = "descriptive-dashboard" if decision.disposition is CohortFoundationDisposition.ALLOW_DESCRIPTIVE else "review-queue" if decision.disposition is CohortFoundationDisposition.REVIEW else "quarantine-store"
        action = "publish aggregate fields" if decision.disposition is CohortFoundationDisposition.ALLOW_DESCRIPTIVE else "retain and request review" if decision.disposition is CohortFoundationDisposition.REVIEW else "withhold from transport"
        body = {"operation": decision.operation, "state": decision.state, "disposition": decision.disposition, "consumer": consumer}
        cells.append(CohortFoundationOperationalCell(decision.operation, decision.state, decision.disposition, consumer, decision.disposition is not CohortFoundationDisposition.QUARANTINE, action, content_hash(body)))
    body = {"matrix_id": "cohort-foundation-frontier-operational", "cells": cells}
    return CohortFoundationOperationalMatrix(body["matrix_id"], tuple(cells), any(item.disposition is CohortFoundationDisposition.QUARANTINE for item in cells) and any(item.disposition is CohortFoundationDisposition.REVIEW for item in cells), content_hash(body))


__all__ = ["CohortFoundationOperationalCell", "CohortFoundationOperationalMatrix", "build_cohort_foundation_frontier_operational_matrix"]
