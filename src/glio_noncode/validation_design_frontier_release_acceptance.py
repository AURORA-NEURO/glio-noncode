"""independent release gate over required receipts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReleaseAcceptancePlane:
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


def build_validation_design_release_acceptance(**kwargs: Any) -> ValidationDesignReleaseAcceptancePlane:
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
    values = {"fixture_id": fixture_id, "evaluation": bool(getattr(evaluation, "accepted", False)), "quality": bool(getattr(quality, "accepted", False)), "depth": bool(getattr(depth, "accepted", False)), "integrity": bool(getattr(integrity, "accepted", False)), "public": bool(getattr(access, "content_address", "").startswith("sha256:"))}
    accepted = bool(all(values.values()))
    body = {"plane_id": "release_acceptance", "values": values, "accepted": accepted}
    return ValidationDesignReleaseAcceptancePlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReleaseAcceptancePlane", "build_validation_design_release_acceptance"]
