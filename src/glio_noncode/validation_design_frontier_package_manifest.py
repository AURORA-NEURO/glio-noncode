"""operation package manifest."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignPackageManifestPlane:
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


def build_validation_design_package_manifest(**kwargs: Any) -> ValidationDesignPackageManifestPlane:
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
    values = {"operations": tuple(sorted({row.operation.value for row in getattr(evaluation, "executions", ())})), "package_count": len({row.operation for row in getattr(evaluation, "executions", ())}), "fixture_id": fixture_id, "bounded": True}
    accepted = bool(values["package_count"] == 4 and values["bounded"])
    body = {"plane_id": "package_manifest", "values": values, "accepted": accepted}
    return ValidationDesignPackageManifestPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignPackageManifestPlane", "build_validation_design_package_manifest"]
