"""state to operational action map."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignOperationalPlane:
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


def build_editing_design_operational(**kwargs: Any) -> EditingDesignOperationalPlane:
    fixture = kwargs.get("fixture")
    evaluation = kwargs.get("evaluation")
    quality = kwargs.get("quality")
    integrity = kwargs.get("integrity")
    depth = kwargs.get("depth")
    access = kwargs.get("access")
    adapters = kwargs.get("adapters")
    schema = kwargs.get("schema")
    audit = kwargs.get("audit")
    sources = tuple(getattr(fixture, "sources", ()))
    stages = tuple(kwargs.get("stages", ()))
    steps = tuple(kwargs.get("steps", ()))
    run_id = str(kwargs.get("run_id", "editing-design-runtime"))
    fixture_id = str(getattr(fixture, "fixture_id", ""))
    values = {"actions": {"designed": "retain", "review": "route", "blocked": "quarantine", "rejected": "repair"}, "observed": tuple(sorted({row.observed_state.value for row in getattr(evaluation, "executions", ())})), "mapped": True}
    accepted = bool(values["mapped"] and all(state in values["actions"] for state in values["observed"]))
    body = {"plane_id": "operational", "values": values, "accepted": accepted}
    return EditingDesignOperationalPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignOperationalPlane", "build_editing_design_operational"]
