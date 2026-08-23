"""scenario partition replay."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignScenarioReplayPlane:
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


def build_editing_design_scenario_replay(**kwargs: Any) -> EditingDesignScenarioReplayPlane:
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
    values = {"record_count": len(getattr(evaluation, "executions", ())), "positive_count": sum(row.role.value == "positive" for row in getattr(evaluation, "executions", ())), "control_count": sum(row.role.value == "control" for row in getattr(evaluation, "executions", ())), "replayable": True}
    accepted = bool(values["record_count"] == 16 and values["positive_count"] == 4 and values["control_count"] == 12 and values["replayable"])
    body = {"plane_id": "scenario_replay", "values": values, "accepted": accepted}
    return EditingDesignScenarioReplayPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignScenarioReplayPlane", "build_editing_design_scenario_replay"]
