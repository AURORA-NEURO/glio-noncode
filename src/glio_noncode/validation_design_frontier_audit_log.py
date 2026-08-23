"""append-only sequence audit for runtime stages."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignAuditLogPlane:
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


def build_validation_design_audit_log(**kwargs: Any) -> ValidationDesignAuditLogPlane:
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
    values = {"run_id": run_id, "sequences": tuple(getattr(stage, "sequence", 0) for stage in stages), "contiguous": tuple(getattr(stage, "sequence", 0) for stage in stages) == tuple(range(1, len(stages) + 1)), "unique_stage_ids": len({getattr(stage, "stage_id", "") for stage in stages}) == len(stages), "stage_count": len(stages)}
    accepted = bool(values["contiguous"] and values["unique_stage_ids"])
    body = {"plane_id": "audit_log", "values": values, "accepted": accepted}
    return ValidationDesignAuditLogPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignAuditLogPlane", "build_validation_design_audit_log"]
