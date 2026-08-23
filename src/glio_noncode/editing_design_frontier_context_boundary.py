"""exact context partition audit."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignContextBoundaryPlane:
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


def build_editing_design_context_boundary(**kwargs: Any) -> EditingDesignContextBoundaryPlane:
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
    values = {"fixture_context": getattr(fixture, "context_key", ""), "record_contexts": tuple(sorted({row.context_key for row in getattr(fixture, "records", ())})), "foreign_contexts": tuple(sorted({row.context_key for row in getattr(fixture, "records", ()) if row.context_key != getattr(fixture, "context_key", "")})), "declared": True}
    accepted = bool(values["declared"] and values["fixture_context"] and len(values["foreign_contexts"]) == 1)
    body = {"plane_id": "context_boundary", "values": values, "accepted": accepted}
    return EditingDesignContextBoundaryPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignContextBoundaryPlane", "build_editing_design_context_boundary"]
