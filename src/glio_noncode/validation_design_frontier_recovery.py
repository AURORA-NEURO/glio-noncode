"""state-to-action recovery map for held planning rows."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignRecoveryPlane:
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


def build_validation_design_recovery(**kwargs: Any) -> ValidationDesignRecoveryPlane:
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
    values = {"state_actions": {"ready": "retain", "routed": "retain", "packaged": "retain", "review": "assign reviewer", "blocked": "quarantine context", "rejected": "repair payload"}, "observed_states": tuple(sorted({row.observed_state.value for row in getattr(evaluation, "executions", ())})), "review_count": sum(row.observed_state.value == "review" for row in getattr(evaluation, "executions", ())), "blocked_count": sum(row.observed_state.value == "blocked" for row in getattr(evaluation, "executions", ()))}
    accepted = bool(all(values["state_actions"].get(state) for state in values["observed_states"]))
    body = {"plane_id": "recovery", "values": values, "accepted": accepted}
    return ValidationDesignRecoveryPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignRecoveryPlane", "build_validation_design_recovery"]
