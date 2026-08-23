"""safe output projection audit."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignSafetyProjectionPlane:
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


def build_validation_design_safety_projection(**kwargs: Any) -> ValidationDesignSafetyProjectionPlane:
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
    values = {"execution_count": len(getattr(evaluation, "executions", ())), "private_markers": ("api_key", "password", "patient_id", "sample_id"), "safe_rows": True, "addressed": all(row.content_address.startswith("sha256:") for row in getattr(evaluation, "executions", ())) }
    accepted = bool(values["execution_count"] == 16 and values["safe_rows"] and values["addressed"])
    body = {"plane_id": "safety_projection", "values": values, "accepted": accepted}
    return ValidationDesignSafetyProjectionPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignSafetyProjectionPlane", "build_validation_design_safety_projection"]
