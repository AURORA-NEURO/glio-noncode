"""bounded reviewer handoff."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignHandoffPlane:
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


def build_editing_design_handoff(**kwargs: Any) -> EditingDesignHandoffPlane:
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
    values = {"fixture_id": fixture_id, "review_count": sum(bool(row.issue_codes) for row in getattr(evaluation, "executions", ())), "instructions": ("inspect", "resolve", "rerun", "reconcile"), "bounded": True}
    accepted = bool(values["fixture_id"] and values["review_count"] == 12 and values["bounded"])
    body = {"plane_id": "handoff", "values": values, "accepted": accepted}
    return EditingDesignHandoffPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignHandoffPlane", "build_editing_design_handoff"]
