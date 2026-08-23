"""state transition vocabulary audit."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignStateTransitionPlane:
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


def build_validation_design_state_transition(**kwargs: Any) -> ValidationDesignStateTransitionPlane:
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
    values = {"states": tuple(sorted({row.observed_state.value for row in getattr(evaluation, "executions", ())})), "allowed": ("ready", "review", "blocked", "routed", "packaged", "rejected", "abstained"), "valid": all(state in ("ready", "review", "blocked", "routed", "packaged", "rejected", "abstained") for state in {row.observed_state.value for row in getattr(evaluation, "executions", ())}), "transition_count": len(getattr(evaluation, "executions", ())) }
    accepted = bool(values["valid"] and values["transition_count"] == 16)
    body = {"plane_id": "state_transition", "values": values, "accepted": accepted}
    return ValidationDesignStateTransitionPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignStateTransitionPlane", "build_validation_design_state_transition"]
