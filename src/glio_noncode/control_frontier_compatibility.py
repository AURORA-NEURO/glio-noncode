"""Version and contract compatibility checks for control frontier consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_adapters import ControlFrontierAdapterRegistry
from .control_frontier_contracts import CONTROL_FRONTIER_VERSION
from .control_frontier_schema import ControlFrontierSchema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierCompatibilityReport:
    requested_version: str
    current_version: str
    schema_id: str
    adapter_count: int
    compatible: bool
    blockers: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_control_frontier_compatibility(requested_version: str, schema: ControlFrontierSchema, adapters: ControlFrontierAdapterRegistry) -> ControlFrontierCompatibilityReport:
    blockers = []
    if requested_version != CONTROL_FRONTIER_VERSION:
        blockers.append("version_mismatch")
    if len(adapters.specs) != 8:
        blockers.append("adapter_count")
    if schema.schema_id != "control-frontier-public-receipts":
        blockers.append("schema_id")
    body = {"requested_version": requested_version, "current_version": CONTROL_FRONTIER_VERSION, "schema_id": schema.schema_id, "adapter_count": len(adapters.specs), "compatible": not blockers, "blockers": tuple(blockers)}
    return ControlFrontierCompatibilityReport(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierCompatibilityReport", "evaluate_control_frontier_compatibility"]
