"""Stable row views for review queues and planning summaries."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignView:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_view(evaluation: Any) -> ValidationDesignView:
    rows = tuple({"record_id": item.record_id, "capability": item.capability, "operation": item.operation.value, "role": item.role.value, "state": item.observed_state.value, "issue_codes": item.issue_codes, "output_keys": tuple(sorted(item.output)), "content_address": item.content_address} for item in evaluation.executions)
    body = {"rows": rows, "accepted": len(rows) == 16 and all(row["content_address"].startswith("sha256:") for row in rows)}
    return ValidationDesignView(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignView", "build_validation_design_view"]
