"""Stable row projection for reviewers and exports."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseView:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_view(evaluation: Any) -> WorkbenchReleaseView:
    rows = tuple({"record_id": item.record_id, "capability": item.capability, "operation": item.operation.value, "role": item.role.value, "state": item.observed_state.value, "issues": item.issue_codes, "content_address": item.content_address} for item in evaluation.executions)
    body = {"rows": rows, "accepted": len(rows) == len(evaluation.executions)}
    return WorkbenchReleaseView(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseView", "build_workbench_release_view"]
