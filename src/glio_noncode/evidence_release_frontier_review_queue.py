"""Review queue routing for non-terminal lifecycle rows."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseReviewQueue:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_review_queue(evaluation: Any) -> EvidenceReleaseReviewQueue:
    rows = tuple({"record_id": row.record_id, "operation": row.operation.value, "priority": "high" if row.observed_state.value == "blocked" else "normal", "issue_codes": row.issue_codes} for row in evaluation.executions if row.observed_state.value in {"review", "blocked", "rejected"})
    body = {"rows": rows, "accepted": all(item["record_id"] for item in rows)}
    return EvidenceReleaseReviewQueue(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseReviewQueue", "build_evidence_release_review_queue"]
