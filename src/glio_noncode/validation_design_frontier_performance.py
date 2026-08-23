"""bounded local resource accounting for evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignPerformancePlane:
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


def build_validation_design_performance(**kwargs: Any) -> ValidationDesignPerformancePlane:
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
    values = {"row_count": len(getattr(evaluation, "executions", ())), "check_count": len(getattr(evaluation, "checks", ())), "address_bytes": sum(len(getattr(row, "content_address", "")) for row in getattr(evaluation, "executions", ())), "bounded_rows": len(getattr(evaluation, "executions", ())) <= 10000, "bounded_checks": len(getattr(evaluation, "checks", ())) <= 100000}
    accepted = bool(values["bounded_rows"] and values["bounded_checks"] and values["row_count"] == 16)
    body = {"plane_id": "performance", "values": values, "accepted": accepted}
    return ValidationDesignPerformancePlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignPerformancePlane", "build_validation_design_performance"]
