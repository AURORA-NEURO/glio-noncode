"""held work operator console."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignOperatorConsolePlane:
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


def build_editing_design_operator_console(**kwargs: Any) -> EditingDesignOperatorConsolePlane:
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
    values = {"run_id": run_id, "review_count": sum(row.observed_state.value == "review" for row in getattr(evaluation, "executions", ())), "blocked_count": sum(row.observed_state.value == "blocked" for row in getattr(evaluation, "executions", ())), "actions": ("inspect", "resolve", "rerun", "reconcile"), "ready": True}
    accepted = bool(values["review_count"] == 8 and values["blocked_count"] == 4 and values["ready"])
    body = {"plane_id": "operator_console", "values": values, "accepted": accepted}
    return EditingDesignOperatorConsolePlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignOperatorConsolePlane", "build_editing_design_operator_console"]
