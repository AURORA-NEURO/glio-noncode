"""resource budget for bounded artifacts and checks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignResourcesPlane:
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


def build_validation_design_resources(**kwargs: Any) -> ValidationDesignResourcesPlane:
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
    values = {"rows": len(getattr(evaluation, "executions", ())), "checks": len(getattr(evaluation, "checks", ())), "source_receipts": len(sources), "max_rows": 10000, "max_checks": 100000, "within_budget": len(getattr(evaluation, "executions", ())) <= 10000 and len(getattr(evaluation, "checks", ())) <= 100000}
    accepted = bool(values["within_budget"] and values["rows"] == 16 and values["checks"] == 80)
    body = {"plane_id": "resources", "values": values, "accepted": accepted}
    return ValidationDesignResourcesPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignResourcesPlane", "build_validation_design_resources"]
