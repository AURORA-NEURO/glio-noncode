"""operator action matrix for every outcome state."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignOperationalPlane:
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


def build_validation_design_operational(**kwargs: Any) -> ValidationDesignOperationalPlane:
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
    values = {"actions": {"ready": "retain plan", "routed": "retain route", "packaged": "retain manifest", "review": "route to reviewer", "blocked": "quarantine", "rejected": "repair payload"}, "states": tuple(sorted({row.observed_state.value for row in getattr(evaluation, "executions", ())})), "all_mapped": True, "run_id": run_id}
    accepted = bool(all(values["actions"].get(state) for state in values["states"]))
    body = {"plane_id": "operational", "values": values, "accepted": accepted}
    return ValidationDesignOperationalPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignOperationalPlane", "build_validation_design_operational"]
