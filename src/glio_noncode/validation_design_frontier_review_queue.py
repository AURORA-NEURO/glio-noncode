"""Priority queue for review and blocked planning records."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReviewQueue:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_review_queue(evaluation: Any) -> ValidationDesignReviewQueue:
    rows = []
    for item in evaluation.executions:
        if item.observed_state.value in {"review", "blocked", "rejected"}:
            priority = "high" if item.observed_state.value in {"blocked", "rejected"} else "normal"
            rows.append({"queue_id": f"queue:{item.record_id}", "record_id": item.record_id, "operation": item.operation.value, "state": item.observed_state.value, "issue_codes": item.issue_codes, "priority": priority, "instruction": "resolve issue codes and rerun exact payload"})
    rows = tuple(rows)
    body = {"rows": rows, "accepted": all(row["queue_id"].startswith("queue:") for row in rows)}
    return ValidationDesignReviewQueue(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReviewQueue", "build_validation_design_review_queue"]
