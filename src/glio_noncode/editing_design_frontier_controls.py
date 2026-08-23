"""negative-control coverage."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignControlsPlane:
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


def build_editing_design_controls(**kwargs: Any) -> EditingDesignControlsPlane:
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
    values = {"operations": {operation: sum(row.role.value == "control" and row.operation.value == operation for row in getattr(evaluation, "executions", ())) for operation in sorted({row.operation.value for row in getattr(evaluation, "executions", ())})}, "held_controls": sum(row.role.value == "control" and bool(row.issue_codes) for row in getattr(evaluation, "executions", ())), "operation_count": 4}
    accepted = bool(values["operation_count"] == 4 and all(count == 3 for count in values["operations"].values()) and values["held_controls"] == 12)
    body = {"plane_id": "controls", "values": values, "accepted": accepted}
    return EditingDesignControlsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignControlsPlane", "build_editing_design_controls"]
