"""Reviewer handoff with queue IDs and operation metrics."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseHandoff:
    fixture_id: str
    review_ids: tuple[str, ...]
    blocked_ids: tuple[str, ...]
    metrics: dict[str, Any]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_handoff(fixture: Any, evaluation: Any, metrics: Any, queue: Any) -> WorkbenchReleaseHandoff:
    review_ids = tuple(item["record_id"] for item in queue.rows)
    blocked_ids = tuple(item.record_id for item in evaluation.executions if item.observed_state.value == "blocked")
    summary = {"row_count": metrics.row_count, "state_counts": metrics.state_counts, "operation_counts": metrics.operation_counts, "review_count": len(review_ids), "blocked_count": len(blocked_ids)}
    body = {"fixture_id": fixture.fixture_id, "review_ids": review_ids, "blocked_ids": blocked_ids, "metrics": summary, "accepted": bool(fixture.fixture_id)}
    return WorkbenchReleaseHandoff(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseHandoff", "build_workbench_release_handoff"]
