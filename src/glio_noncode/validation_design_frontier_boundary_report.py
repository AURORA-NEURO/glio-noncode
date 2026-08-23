"""final boundary report for release interpretation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignBoundaryReportPlane:
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


def build_validation_design_boundary_report(**kwargs: Any) -> ValidationDesignBoundaryReportPlane:
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
    values = {"context": getattr(fixture, "context_key", ""), "evidence_boundary": getattr(fixture, "evidence_boundary", ""), "research_only": True, "unsupported": ("clinical efficacy", "individual diagnosis", "causal certainty"), "declared": True}
    accepted = bool(values["declared"] and values["research_only"] and values["evidence_boundary"] == "public_aggregate_validation_design_planning")
    body = {"plane_id": "boundary_report", "values": values, "accepted": accepted}
    return ValidationDesignBoundaryReportPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignBoundaryReportPlane", "build_validation_design_boundary_report"]
