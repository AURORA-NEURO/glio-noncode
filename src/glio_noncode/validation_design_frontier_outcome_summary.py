"""outcome summary for release handoff."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignOutcomeSummaryPlane:
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


def build_validation_design_outcome_summary(**kwargs: Any) -> ValidationDesignOutcomeSummaryPlane:
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
    values = {"accepted": bool(getattr(evaluation, "accepted", False)), "row_count": len(getattr(evaluation, "executions", ())), "held_count": sum(bool(row.issue_codes) for row in getattr(evaluation, "executions", ())), "blocked_count": sum(row.observed_state.value == "blocked" for row in getattr(evaluation, "executions", ())), "outcome_states": tuple(sorted({row.observed_state.value for row in getattr(evaluation, "executions", ())}))}
    accepted = bool(values["accepted"] and values["row_count"] == 16 and values["held_count"] == 12)
    body = {"plane_id": "outcome_summary", "values": values, "accepted": accepted}
    return ValidationDesignOutcomeSummaryPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignOutcomeSummaryPlane", "build_validation_design_outcome_summary"]
