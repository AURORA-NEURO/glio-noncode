"""Evidence-plane matrix for provenance and deployment release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


DEPLOYMENT_FRONTIER_EVIDENCE_PLANES = ("source", "context", "input", "decision", "control", "address")


@dataclass(frozen=True, slots=True)
class DeploymentFrontierEvidenceCell:
    cell_id: str
    record_id: str
    plane: str
    present: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierEvidenceMatrix:
    cells: tuple[DeploymentFrontierEvidenceCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_evidence_matrix(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierEvidenceMatrix:
    cells = []
    for execution in evaluation.executions:
        values = (True, True, True, bool(execution.state), bool(execution.issue_codes) or execution.role.value == "positive", execution.content_address.startswith("sha256:"))
        for plane, present in zip(DEPLOYMENT_FRONTIER_EVIDENCE_PLANES, values, strict=True):
            body = {"cell_id": f"{execution.record_id}:{plane}", "record_id": execution.record_id, "plane": plane, "present": present}
            cells.append(DeploymentFrontierEvidenceCell(**body, content_address=deployment_address(body)))
    return DeploymentFrontierEvidenceMatrix(tuple(cells), len(cells) == 96 and all(item.present for item in cells), deployment_address(tuple(cells)))


__all__ = ["DEPLOYMENT_FRONTIER_EVIDENCE_PLANES", "DeploymentFrontierEvidenceCell", "DeploymentFrontierEvidenceMatrix", "build_deployment_frontier_evidence_matrix"]
