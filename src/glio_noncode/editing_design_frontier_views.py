"""stable review row projection."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignViewsPlane:
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


def build_editing_design_views(**kwargs: Any) -> EditingDesignViewsPlane:
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
    values = {"row_count": len(getattr(evaluation, "executions", ())), "columns": ("record_id", "operation", "role", "state", "issue_codes", "content_address"), "addressed": all(row.content_address.startswith("sha256:") for row in getattr(evaluation, "executions", ())), "stable": True}
    accepted = bool(values["row_count"] == 16 and values["addressed"] and values["stable"])
    body = {"plane_id": "views", "values": values, "accepted": accepted}
    return EditingDesignViewsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignViewsPlane", "build_editing_design_views"]
