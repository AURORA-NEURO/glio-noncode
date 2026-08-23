"""ordered run manifest with stable stage identities."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignRunManifestPlane:
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


def build_validation_design_run_manifest(**kwargs: Any) -> ValidationDesignRunManifestPlane:
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
    values = {"run_id": run_id, "fixture_id": fixture_id, "stages": tuple(getattr(stage, "stage_id", str(stage)) for stage in stages), "stage_count": len(stages), "ordered": tuple(getattr(stage, "sequence", 0) for stage in stages) == tuple(range(1, len(stages) + 1))}
    accepted = bool(bool(run_id) and values["stage_count"] >= 1 and values["ordered"])
    body = {"plane_id": "run_manifest", "values": values, "accepted": accepted}
    return ValidationDesignRunManifestPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignRunManifestPlane", "build_validation_design_run_manifest"]
