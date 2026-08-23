"""claim boundary for research-only planning interpretation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignClaimBoundaryPlane:
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


def build_validation_design_claim_boundary(**kwargs: Any) -> ValidationDesignClaimBoundaryPlane:
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
    values = {"boundary": "public aggregate planning", "research_only": True, "prohibited": ("clinical efficacy", "individual diagnosis", "causal certainty", "patient-level inference"), "fixture_boundary": getattr(fixture, "evidence_boundary", "")}
    accepted = bool(values["research_only"] and values["fixture_boundary"] == "public_aggregate_validation_design_planning")
    body = {"plane_id": "claim_boundary", "values": values, "accepted": accepted}
    return ValidationDesignClaimBoundaryPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignClaimBoundaryPlane", "build_validation_design_claim_boundary"]
