"""Output projection policy for safe, bounded planning artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .planning_frontier_support import contains_private_marker, safe_output
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class OutputProjection:
    projected: Any
    private_marker_found_before_projection: bool
    private_marker_found_after_projection: bool
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def project_planning_output(value: Any) -> OutputProjection:
    before = contains_private_marker(value)
    projected = safe_output(value)
    after = contains_private_marker(projected)
    body = {"projected": projected, "private_marker_found_before_projection": before, "private_marker_found_after_projection": after, "accepted": not after}
    return OutputProjection(**body, content_address=content_hash(body, prefix="output-projection"))
__all__ = ["OutputProjection", "project_planning_output"]
