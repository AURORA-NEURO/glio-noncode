"""Version and migration receipts for the control frontier contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .control_frontier_contracts import CONTROL_FRONTIER_VERSION
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierVersionReceipt:
    fixture_id: str
    observed_version: str
    required_version: str
    compatible: bool
    migration_path: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def inspect_control_frontier_version(payload: Mapping[str, Any]) -> ControlFrontierVersionReceipt:
    """Inspect version metadata without mutating the serialized payload."""

    fixture_id = str(payload.get("fixture_id", ""))
    observed = str(payload.get("fixture_version", ""))
    if not fixture_id or not observed:
        raise ValidationError("control frontier version receipt requires fixture metadata")
    compatible = observed == CONTROL_FRONTIER_VERSION
    migration_path = () if compatible else (f"{observed}->{CONTROL_FRONTIER_VERSION}",)
    body = {"fixture_id": fixture_id, "observed_version": observed, "required_version": CONTROL_FRONTIER_VERSION, "compatible": compatible, "migration_path": migration_path}
    return ControlFrontierVersionReceipt(**body, content_address=content_hash(body))


def migrate_control_frontier_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with current metadata while preserving row content."""

    receipt = inspect_control_frontier_version(payload)
    migrated = dict(payload)
    migrated["fixture_version"] = CONTROL_FRONTIER_VERSION
    migrated["migration_receipt"] = receipt.content_address
    return migrated


__all__ = ["ControlFrontierVersionReceipt", "inspect_control_frontier_version", "migrate_control_frontier_metadata"]
