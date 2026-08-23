"""four-operation and eighty-check depth audit."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignDepthPlane:
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


def build_editing_design_depth(**kwargs: Any) -> EditingDesignDepthPlane:
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
    values = {"source_count": len(sources), "row_count": len(getattr(fixture, "records", ())), "operation_count": len({row.operation for row in getattr(fixture, "records", ())}), "check_count": len(getattr(evaluation, "checks", ())), "role_counts": (len(getattr(fixture, "positive_records", ())), len(getattr(fixture, "control_records", ())))}
    accepted = bool(values["source_count"] == 5 and values["row_count"] == 16 and values["operation_count"] == 4 and values["check_count"] == 80 and values["role_counts"] == (4, 12))
    body = {"plane_id": "depth", "values": values, "accepted": accepted}
    return EditingDesignDepthPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignDepthPlane", "build_editing_design_depth"]
