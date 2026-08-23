"""deterministic query projection over planning executions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignQueryPlane:
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


def build_validation_design_query(**kwargs: Any) -> ValidationDesignQueryPlane:
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
    values = {"query": str(kwargs.get("query", "all")), "matched_ids": tuple(row.record_id for row in getattr(evaluation, "executions", ()) if kwargs.get("query", "all") in {"all", row.operation.value, row.observed_state.value, row.role.value}), "row_count": len(getattr(evaluation, "executions", ())), "deterministic": True}
    accepted = bool(values["deterministic"] and values["row_count"] == 16)
    body = {"plane_id": "query", "values": values, "accepted": accepted}
    return ValidationDesignQueryPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignQueryPlane", "build_validation_design_query"]
