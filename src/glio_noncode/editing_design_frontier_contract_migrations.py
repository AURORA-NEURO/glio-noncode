"""contract version compatibility."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignContractMigrationsPlane:
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


def build_editing_design_contract_migrations(**kwargs: Any) -> EditingDesignContractMigrationsPlane:
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
    values = {"current": getattr(fixture, "fixture_version", ""), "supported": ("2026.08.d13-c05-c08.v1",), "migration_required": False, "compatible": getattr(fixture, "fixture_version", "") in ("2026.08.d13-c05-c08.v1",)}
    accepted = bool(values["compatible"] and not values["migration_required"])
    body = {"plane_id": "contract_migrations", "values": values, "accepted": accepted}
    return EditingDesignContractMigrationsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignContractMigrationsPlane", "build_editing_design_contract_migrations"]
