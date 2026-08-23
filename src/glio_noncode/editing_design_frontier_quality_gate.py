"""blocking quality gate."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignQualityGatePlane:
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


def build_editing_design_quality_gate(**kwargs: Any) -> EditingDesignQualityGatePlane:
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
    values = {"audit": bool(getattr(kwargs.get("audit"), "accepted", False)), "evaluation": bool(getattr(evaluation, "accepted", False)), "schema": getattr(schema, "version", "") == "editing-design-schema-v1", "adapters": len(getattr(adapters, "adapters", ())) == 4, "closed": True}
    accepted = bool(all(values.values()))
    body = {"plane_id": "quality_gate", "values": values, "accepted": accepted}
    return EditingDesignQualityGatePlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignQualityGatePlane", "build_editing_design_quality_gate"]
