"""Validation matrix: state, issue, safety, address, and context coverage."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseValidationMatrix:
    cells: tuple[dict[str, Any], ...]
    cell_count: int
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_validation_matrix(evaluation: Any) -> EvidenceReleaseValidationMatrix:
    planes = ("state", "issue", "role", "integrity", "safety")
    cells = tuple({"record_id": row.record_id, "plane": plane, "passed": next((check.passed for check in evaluation.checks if check.record_id == row.record_id and check.plane == plane), False)} for row in evaluation.executions for plane in planes)
    body = {"cells": cells, "cell_count": len(cells), "accepted": all(item["passed"] for item in cells)}
    return EvidenceReleaseValidationMatrix(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseValidationMatrix", "build_evidence_release_validation_matrix"]
