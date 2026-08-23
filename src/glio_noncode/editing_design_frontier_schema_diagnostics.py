"""schema completeness diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignSchemaDiagnosticsPlane:
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


def build_editing_design_schema_diagnostics(**kwargs: Any) -> EditingDesignSchemaDiagnosticsPlane:
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
    values = {"version": getattr(schema, "version", ""), "operation_count": len(getattr(schema, "required_fields", {})), "complete": all(value for value in getattr(schema, "required_fields", {}).values())}
    accepted = bool(values["version"] == "editing-design-schema-v1" and values["operation_count"] == 4 and values["complete"])
    body = {"plane_id": "schema_diagnostics", "values": values, "accepted": accepted}
    return EditingDesignSchemaDiagnosticsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignSchemaDiagnosticsPlane", "build_editing_design_schema_diagnostics"]
