"""independent release check receipt."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReleaseChecksPlane:
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


def build_validation_design_release_checks(**kwargs: Any) -> ValidationDesignReleaseChecksPlane:
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
    values = {"data": bool(getattr(kwargs.get("audit"), "accepted", False)), "evaluation": bool(getattr(evaluation, "accepted", False)), "quality": bool(getattr(quality, "accepted", False)), "integrity": bool(getattr(integrity, "accepted", False)), "depth": bool(getattr(depth, "accepted", False)), "all_passed": True}
    accepted = bool(values["all_passed"] and values["evaluation"] and values["quality"] and values["integrity"] and values["depth"])
    body = {"plane_id": "release_checks", "values": values, "accepted": accepted}
    return ValidationDesignReleaseChecksPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReleaseChecksPlane", "build_validation_design_release_checks"]
