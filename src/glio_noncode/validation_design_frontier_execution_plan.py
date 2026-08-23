"""dependency order for deterministic runtime planes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignExecutionPlanPlane:
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


def build_validation_design_execution_plan(**kwargs: Any) -> ValidationDesignExecutionPlanPlane:
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
    values = {"fixture_id": fixture_id, "steps": tuple(steps), "unique": len(steps) == len(set(steps)), "first": steps[0] if steps else "", "last": steps[-1] if steps else "", "count": len(steps)}
    accepted = bool(values["count"] >= 10 and values["unique"])
    body = {"plane_id": "execution_plan", "values": values, "accepted": accepted}
    return ValidationDesignExecutionPlanPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignExecutionPlanPlane", "build_validation_design_execution_plan"]
