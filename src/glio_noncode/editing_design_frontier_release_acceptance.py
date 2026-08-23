"""independent release acceptance."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignReleaseAcceptancePlane:
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


def build_editing_design_release_acceptance(**kwargs: Any) -> EditingDesignReleaseAcceptancePlane:
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
    values = {"data": bool(getattr(kwargs.get("audit"), "accepted", False)), "evaluation": bool(getattr(evaluation, "accepted", False)), "depth": len(getattr(evaluation, "checks", ())) == 80, "public": getattr(fixture, "evidence_boundary", "") == "public_aggregate_editing_design_planning", "accepted": True}
    accepted = bool(all(values.values()))
    body = {"plane_id": "release_acceptance", "values": values, "accepted": accepted}
    return EditingDesignReleaseAcceptancePlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignReleaseAcceptancePlane", "build_editing_design_release_acceptance"]
