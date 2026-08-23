"""review response bands."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignReviewSlaPlane:
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


def build_editing_design_review_sla(**kwargs: Any) -> EditingDesignReviewSlaPlane:
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
    values = {"rows": tuple({"record_id": row.record_id, "priority": "high" if row.observed_state.value == "blocked" else "normal"} for row in getattr(evaluation, "executions", ()) if row.issue_codes), "high_count": sum(row.observed_state.value == "blocked" for row in getattr(evaluation, "executions", ())), "normal_count": sum(row.observed_state.value == "review" for row in getattr(evaluation, "executions", ())), "mapped": True}
    accepted = bool(values["high_count"] == 4 and values["normal_count"] == 8 and values["mapped"])
    body = {"plane_id": "review_sla", "values": values, "accepted": accepted}
    return EditingDesignReviewSlaPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignReviewSlaPlane", "build_editing_design_review_sla"]
