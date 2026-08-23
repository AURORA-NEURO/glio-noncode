"""Queue index used by runtime query and review routing."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseQueueIndex:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_queue(evaluation: Any) -> WorkbenchReleaseQueueIndex:
    rows = tuple({"record_id": item.record_id, "operation": item.operation.value, "state": item.observed_state.value, "priority": "high" if item.observed_state.value == "blocked" else "normal"} for item in evaluation.executions if item.observed_state.value in {"review", "blocked", "rejected"})
    body = {"rows": rows, "accepted": len(rows) == sum(item.observed_state.value in {"review", "blocked", "rejected"} for item in evaluation.executions)}
    return WorkbenchReleaseQueueIndex(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseQueueIndex", "build_workbench_release_queue"]
