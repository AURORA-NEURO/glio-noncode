"""Review queue for incomplete forms, empty exports, misses, and failures."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseReviewQueue:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_review_queue(evaluation: Any) -> WorkbenchReleaseReviewQueue:
    rows = tuple({"record_id": row.record_id, "capability": row.capability, "operation": row.operation.value, "priority": "high" if row.observed_state.value == "blocked" else "normal", "issue_codes": row.issue_codes} for row in evaluation.executions if row.observed_state.value in {"review", "blocked", "rejected"})
    body = {"rows": rows, "accepted": all(item["record_id"] for item in rows)}
    return WorkbenchReleaseReviewQueue(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseReviewQueue", "build_workbench_release_review_queue"]
