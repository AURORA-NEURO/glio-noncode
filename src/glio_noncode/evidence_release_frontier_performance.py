"""Local bounded performance budget for deterministic fixture evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleasePerformanceBudget:
    row_count: int
    estimated_operations: int
    bounded: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_performance_budget(evaluation: Any) -> EvidenceReleasePerformanceBudget:
    body = {"row_count": len(evaluation.executions), "estimated_operations": len(evaluation.executions) * 4}
    return EvidenceReleasePerformanceBudget(**body, bounded=body["row_count"] <= 1000, content_address=content_hash(body | {"bounded": body["row_count"] <= 1000}))

__all__ = ["EvidenceReleasePerformanceBudget", "build_evidence_release_performance_budget"]
