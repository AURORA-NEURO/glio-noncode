"""structured run trace and outcome counters."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignObservabilityPlane:
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


def build_validation_design_observability(**kwargs: Any) -> ValidationDesignObservabilityPlane:
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
    values = {"run_id": run_id, "stage_count": len(stages), "completed": all(getattr(stage, "state", "") == "completed" for stage in stages), "addresses": all(getattr(stage, "output_address", "").startswith("sha256:") for stage in stages), "accepted": bool(getattr(evaluation, "accepted", False))}
    accepted = bool(bool(run_id) and values["completed"] and values["addresses"] and values["accepted"])
    body = {"plane_id": "observability", "values": values, "accepted": accepted}
    return ValidationDesignObservabilityPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignObservabilityPlane", "build_validation_design_observability"]
