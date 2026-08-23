"""release receipt for the bounded public planning surface."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReleasePlane:
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


def build_validation_design_release(**kwargs: Any) -> ValidationDesignReleasePlane:
    fixture = kwargs.get("fixture")
    evaluation = kwargs.get("evaluation")
    quality = kwargs.get("quality")
    integrity = kwargs.get("integrity")
    depth = kwargs.get("depth")
    access = kwargs.get("access")
    adapters = kwargs.get("adapters")
    schema = kwargs.get("schema")
    sources = tuple(getattr(fixture, "sources", ()))
    stages = tuple(kwargs.get("stages", ()))
    steps = tuple(kwargs.get("steps", ()))
    run_id = str(kwargs.get("run_id", "validation-design-runtime"))
    fixture_id = str(getattr(fixture, "fixture_id", ""))
    values = {"fixture_id": fixture_id, "evaluation_address": getattr(evaluation, "content_address", ""), "quality": bool(getattr(quality, "accepted", True)), "integrity": bool(getattr(integrity, "accepted", True)), "run_id": run_id}
    accepted = bool(bool(fixture_id) and values["quality"] and values["integrity"])
    body = {"plane_id": "release", "values": values, "accepted": accepted}
    return ValidationDesignReleasePlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReleasePlane", "build_validation_design_release"]
