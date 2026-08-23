"""Version receipts and metadata migration for the platform fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import ValidationError
from .platform_frontier_contracts import PLATFORM_FRONTIER_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierVersionReceipt:
    fixture_id: str
    observed_version: str
    required_version: str
    compatible: bool
    migration_path: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def inspect_platform_frontier_version(payload: Mapping[str, Any]) -> PlatformFrontierVersionReceipt:
    fixture_id, observed = str(payload.get("fixture_id", "")), str(payload.get("fixture_version", ""))
    if not fixture_id or not observed:
        raise ValidationError("platform version receipt requires fixture metadata")
    compatible = observed == PLATFORM_FRONTIER_VERSION
    path = () if compatible else (f"{observed}->{PLATFORM_FRONTIER_VERSION}",)
    body = {"fixture_id": fixture_id, "observed_version": observed, "required_version": PLATFORM_FRONTIER_VERSION, "compatible": compatible, "migration_path": path}
    return PlatformFrontierVersionReceipt(**body, content_address=content_hash(body))


def migrate_platform_frontier_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    receipt = inspect_platform_frontier_version(payload)
    migrated = dict(payload)
    migrated["fixture_version"] = PLATFORM_FRONTIER_VERSION
    migrated["migration_receipt"] = receipt.content_address
    return migrated


__all__ = ["PlatformFrontierVersionReceipt", "inspect_platform_frontier_version", "migrate_platform_frontier_metadata"]
