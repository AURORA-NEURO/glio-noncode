"""bounded editing-design release."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignReleasePlane:
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


def build_editing_design_release(**kwargs: Any) -> EditingDesignReleasePlane:
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
    values = {"fixture_id": fixture_id, "run_id": run_id, "evaluation": bool(getattr(evaluation, "accepted", False)), "quality": bool(getattr(quality, "accepted", True)), "integrity": bool(getattr(integrity, "accepted", True)), "research_only": True}
    accepted = bool(values["fixture_id"] and values["evaluation"] and values["quality"] and values["integrity"] and values["research_only"])
    body = {"plane_id": "release", "values": values, "accepted": accepted}
    return EditingDesignReleasePlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignReleasePlane", "build_editing_design_release"]
