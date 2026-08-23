"""Evidence-plane matrix helpers for bounded release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation
from .serialization import content_hash, jsonable, require_non_empty


LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES = (
    "context",
    "source",
    "operation",
    "state",
    "control",
    "address",
)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierEvidenceCell:
    """One record-by-plane evidence cell."""

    record_id: str
    plane: str
    observed: Any
    complete: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        if self.plane not in LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES:
            raise ValueError("unknown lifecycle evidence plane")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierEvidenceMatrix:
    """Complete row/plane evidence projection."""

    fixture_id: str
    cells: tuple[LifecycleBetaFrontierEvidenceCell, ...]
    accepted: bool
    content_address: str

    def cells_for(self, record_id: str) -> tuple[LifecycleBetaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"plane_count": len(LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES)}


def build_lifecycle_beta_frontier_evidence_matrix(
    evaluation: LifecycleBetaFrontierEvaluation,
) -> LifecycleBetaFrontierEvidenceMatrix:
    """Create six explicit completeness cells for every execution."""

    cells: list[LifecycleBetaFrontierEvidenceCell] = []
    for execution in evaluation.executions:
        values = {
            "context": execution.record_id.split("-")[0],
            "source": execution.record_id,
            "operation": execution.operation.value,
            "state": execution.state.value,
            "control": execution.role.value,
            "address": execution.content_address,
        }
        for plane in LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES:
            body = {"record_id": execution.record_id, "plane": plane, "observed": values[plane], "complete": bool(values[plane])}
            cells.append(LifecycleBetaFrontierEvidenceCell(**body, content_address=content_hash(body)))
    accepted = len(cells) == len(evaluation.executions) * len(LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES) and all(item.complete for item in cells)
    body = {"fixture_id": evaluation.fixture_id, "cells": tuple(cells), "accepted": accepted}
    return LifecycleBetaFrontierEvidenceMatrix(**body, content_address=content_hash(body))


__all__ = [
    "LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES",
    "LifecycleBetaFrontierEvidenceCell",
    "LifecycleBetaFrontierEvidenceMatrix",
    "build_lifecycle_beta_frontier_evidence_matrix",
]
