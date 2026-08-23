"""schema coverage diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignSchemaDiagnosticsPlane:
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


def build_validation_design_schema_diagnostics(**kwargs: Any) -> ValidationDesignSchemaDiagnosticsPlane:
    fixture = kwargs.get("fixture")
    evaluation = kwargs.get("evaluation")
    quality = kwargs.get("quality")
    integrity = kwargs.get("integrity")
    depth = kwargs.get("depth")
    access = kwargs.get("access")
    adapters = kwargs.get("adapters")
    schema = kwargs.get("schema")
    sources = tuple(getattr(fixture, "sources", ()))
    stages = tuple(kwargs.get("stages", ()))
    steps = tuple(kwargs.get("steps", ()))
    run_id = str(kwargs.get("run_id", "validation-design-runtime"))
    fixture_id = str(getattr(fixture, "fixture_id", ""))
    values = {"schema_version": getattr(schema, "version", ""), "operation_count": len(getattr(schema, "required_fields", {})), "required_field_counts": {key: len(value) for key, value in getattr(schema, "required_fields", {}).items()}, "complete": all(value for value in getattr(schema, "required_fields", {}).values())}
    accepted = bool(values["schema_version"] == "validation-design-schema-v1" and values["operation_count"] == 4 and values["complete"])
    body = {"plane_id": "schema_diagnostics", "values": values, "accepted": accepted}
    return ValidationDesignSchemaDiagnosticsPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignSchemaDiagnosticsPlane", "build_validation_design_schema_diagnostics"]
