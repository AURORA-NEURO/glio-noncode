"""release bundle closure across core planning artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignBundlePlane:
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


def build_validation_design_bundle(**kwargs: Any) -> ValidationDesignBundlePlane:
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
    values = {"fixture_address": getattr(fixture, "content_address", ""), "evaluation_address": getattr(evaluation, "content_address", ""), "artifact_address": getattr(kwargs.get("artifacts"), "content_address", ""), "release_address": getattr(kwargs.get("release"), "content_address", ""), "addresses": tuple(address for address in (getattr(fixture, "content_address", ""), getattr(evaluation, "content_address", ""), getattr(kwargs.get("artifacts"), "content_address", ""), getattr(kwargs.get("release"), "content_address", ""))), "closed": True}
    accepted = bool(values["closed"] and all(address.startswith("sha256:") for address in values["addresses"]))
    body = {"plane_id": "bundle", "values": values, "accepted": accepted}
    return ValidationDesignBundlePlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignBundlePlane", "build_validation_design_bundle"]
