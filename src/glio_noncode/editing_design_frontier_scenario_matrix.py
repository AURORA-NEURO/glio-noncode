"""positive and control scenario matrix."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignScenarioMatrixPlane:
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


def build_editing_design_scenario_matrix(**kwargs: Any) -> EditingDesignScenarioMatrixPlane:
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
    values = {"cells": tuple({"operation": operation, "positive": sum(row.role.value == "positive" and row.operation.value == operation for row in getattr(evaluation, "executions", ())), "controls": sum(row.role.value == "control" and row.operation.value == operation for row in getattr(evaluation, "executions", ())), "held": sum(row.role.value == "control" and row.operation.value == operation and bool(row.issue_codes) for row in getattr(evaluation, "executions", ()))} for operation in sorted({row.operation.value for row in getattr(evaluation, "executions", ())})), "cell_count": 4}
    accepted = bool(values["cell_count"] == 4 and all(cell["positive"] == 1 and cell["controls"] == 3 and cell["held"] == 3 for cell in values["cells"]))
    body = {"plane_id": "scenario_matrix", "values": values, "accepted": accepted}
    return EditingDesignScenarioMatrixPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignScenarioMatrixPlane", "build_editing_design_scenario_matrix"]
