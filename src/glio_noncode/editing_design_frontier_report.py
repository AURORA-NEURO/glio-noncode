"""stable aggregate report."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignReportPlane:
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


def build_editing_design_report(**kwargs: Any) -> EditingDesignReportPlane:
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
    values = {"run_id": run_id, "row_count": len(getattr(evaluation, "executions", ())), "state_counts": {state: sum(row.observed_state.value == state for row in getattr(evaluation, "executions", ())) for state in sorted({row.observed_state.value for row in getattr(evaluation, "executions", ())})}, "accepted": bool(getattr(evaluation, "accepted", False))}
    accepted = bool(values["row_count"] == 16 and values["accepted"])
    body = {"plane_id": "report", "values": values, "accepted": accepted}
    return EditingDesignReportPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignReportPlane", "build_editing_design_report"]
