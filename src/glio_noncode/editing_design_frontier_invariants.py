"""cross-plane count and state invariants."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignInvariantsPlane:
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


def build_editing_design_invariants(**kwargs: Any) -> EditingDesignInvariantsPlane:
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
    values = {"rows": len(getattr(fixture, "records", ())), "executions": len(getattr(evaluation, "executions", ())), "checks": len(getattr(evaluation, "checks", ())), "positives": len(getattr(fixture, "positive_records", ())), "controls": len(getattr(fixture, "control_records", ())), "accepted": bool(getattr(evaluation, "accepted", False))}
    accepted = bool(values["rows"] == values["executions"] == 16 and values["checks"] == 80 and values["positives"] == 4 and values["controls"] == 12 and values["accepted"])
    body = {"plane_id": "invariants", "values": values, "accepted": accepted}
    return EditingDesignInvariantsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignInvariantsPlane", "build_editing_design_invariants"]
