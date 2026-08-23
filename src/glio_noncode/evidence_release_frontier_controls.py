"""Negative-control coverage for each transition operation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseControlCoverage:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_control_coverage(evaluation: Any) -> EvidenceReleaseControlCoverage:
    rows = []
    for operation in sorted({item.operation.value for item in evaluation.executions}):
        controls = tuple(item for item in evaluation.executions if item.operation.value == operation and item.role.value == "control")
        rows.append({"operation": operation, "control_count": len(controls), "blocked_or_review": sum(item.observed_state.value in {"blocked", "review", "rejected"} for item in controls), "covered": bool(controls) and all(item.expected_state == item.observed_state for item in controls)})
    body = {"rows": tuple(rows), "accepted": len(rows) == 4 and all(item["covered"] for item in rows)}
    return EvidenceReleaseControlCoverage(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseControlCoverage", "build_evidence_release_control_coverage"]
