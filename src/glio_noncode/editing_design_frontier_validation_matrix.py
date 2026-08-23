"""five-plane row validation matrix."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignValidationMatrixPlane:
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


def build_editing_design_validation_matrix(**kwargs: Any) -> EditingDesignValidationMatrixPlane:
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
    values = {"row_count": len(getattr(evaluation, "executions", ())), "planes": ("state", "issue", "role", "integrity", "safety"), "cell_count": len(getattr(evaluation, "checks", ())), "accepted": bool(getattr(evaluation, "accepted", False))}
    accepted = bool(values["row_count"] == 16 and values["cell_count"] == 80 and len(values["planes"]) == 5 and values["accepted"])
    body = {"plane_id": "validation_matrix", "values": values, "accepted": accepted}
    return EditingDesignValidationMatrixPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignValidationMatrixPlane", "build_editing_design_validation_matrix"]
