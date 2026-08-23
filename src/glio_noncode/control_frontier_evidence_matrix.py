"""Six-plane evidence completeness matrix for control frontier executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .serialization import content_hash, jsonable


CONTROL_FRONTIER_EVIDENCE_PLANES = ("context", "source", "operation", "state", "role", "address")


@dataclass(frozen=True, slots=True)
class ControlFrontierEvidenceCell:
    record_id: str
    plane: str
    observed: Any
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierEvidenceMatrix:
    fixture_id: str
    cells: tuple[ControlFrontierEvidenceCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"cell_count": len(self.cells)}


def build_control_frontier_evidence_matrix(evaluation: ControlFrontierEvaluation) -> ControlFrontierEvidenceMatrix:
    cells = []
    for item in evaluation.executions:
        values = {"context": item.record_id.split("-")[0], "source": item.record_id, "operation": item.operation.value, "state": item.state.value, "role": item.role.value, "address": item.content_address}
        for plane in CONTROL_FRONTIER_EVIDENCE_PLANES:
            body = {"record_id": item.record_id, "plane": plane, "observed": values[plane], "complete": bool(values[plane])}
            cells.append(ControlFrontierEvidenceCell(**body, content_address=content_hash(body)))
    accepted = len(cells) == len(evaluation.executions) * 6 and all(item.complete for item in cells)
    return ControlFrontierEvidenceMatrix(evaluation.fixture_id, tuple(cells), accepted, content_hash(tuple(cells)))


__all__ = ["CONTROL_FRONTIER_EVIDENCE_PLANES", "ControlFrontierEvidenceCell", "ControlFrontierEvidenceMatrix", "build_control_frontier_evidence_matrix"]
