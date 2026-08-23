"""schema and adapter compatibility contract."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignCompatibilityPlane:
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


def build_validation_design_compatibility(**kwargs: Any) -> ValidationDesignCompatibilityPlane:
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
    values = {"schema_version": getattr(schema, "version", ""), "adapter_count": len(getattr(adapters, "adapters", ())), "operations": tuple(adapter.operation.value for adapter in getattr(adapters, "adapters", ())), "required": all(adapter.input_fields for adapter in getattr(adapters, "adapters", ())), "unique_operations": len({adapter.operation for adapter in getattr(adapters, "adapters", ())})}
    accepted = bool(values["schema_version"] == "validation-design-schema-v1" and values["adapter_count"] == 4 and values["unique_operations"] == 4 and values["required"])
    body = {"plane_id": "compatibility", "values": values, "accepted": accepted}
    return ValidationDesignCompatibilityPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignCompatibilityPlane", "build_validation_design_compatibility"]
