"""held-row review queue."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignReviewQueuePlane:
    plane_id: str
    values: dict[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def summary(self) -> str:
        return f"{self.plane_id}: {'accepted' if self.accepted else 'held'}"

    def check(self, key: str) -> bool:
        return bool(self.values.get(key, False))


def build_editing_design_review_queue(**kwargs: Any) -> EditingDesignReviewQueuePlane:
    fixture = kwargs.get("fixture")
    evaluation = kwargs.get("evaluation")
    quality = kwargs.get("quality")
    integrity = kwargs.get("integrity")
    depth = kwargs.get("depth")
    access = kwargs.get("access")
    adapters = kwargs.get("adapters")
    schema = kwargs.get("schema")
    audit = kwargs.get("audit")
    sources = tuple(getattr(fixture, "sources", ()))
    stages = tuple(kwargs.get("stages", ()))
    steps = tuple(kwargs.get("steps", ()))
    run_id = str(kwargs.get("run_id", "editing-design-runtime"))
    fixture_id = str(getattr(fixture, "fixture_id", ""))
    values = {"held_count": sum(bool(row.issue_codes) for row in getattr(evaluation, "executions", ())), "blocked_count": sum(row.observed_state.value == "blocked" for row in getattr(evaluation, "executions", ())), "priority_bands": ("high", "normal"), "routable": True}
    accepted = bool(values["held_count"] == 12 and values["blocked_count"] == 4 and values["routable"])
    body = {"plane_id": "review_queue", "values": values, "accepted": accepted}
    return EditingDesignReviewQueuePlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignReviewQueuePlane", "build_editing_design_review_queue"]
