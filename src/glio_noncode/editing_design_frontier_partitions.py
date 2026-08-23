"""operation and state partitions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignPartitionsPlane:
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


def build_editing_design_partitions(**kwargs: Any) -> EditingDesignPartitionsPlane:
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
    values = {"by_operation": {operation: tuple(row.record_id for row in getattr(evaluation, "executions", ()) if row.operation.value == operation) for operation in sorted({row.operation.value for row in getattr(evaluation, "executions", ())})}, "by_state": {state: tuple(row.record_id for row in getattr(evaluation, "executions", ()) if row.observed_state.value == state) for state in sorted({row.observed_state.value for row in getattr(evaluation, "executions", ())})}, "operation_count": len({row.operation for row in getattr(evaluation, "executions", ())}), "row_count": len(getattr(evaluation, "executions", ())) }
    accepted = bool(values["operation_count"] == 4 and sum(len(rows) for rows in values["by_operation"].values()) == values["row_count"])
    body = {"plane_id": "partitions", "values": values, "accepted": accepted}
    return EditingDesignPartitionsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignPartitionsPlane", "build_editing_design_partitions"]
