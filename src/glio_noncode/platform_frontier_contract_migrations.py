"""Explicit field migrations for platform contract versions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .platform_frontier_contracts import PLATFORM_FRONTIER_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierMigrationStep:
    migration_id: str
    from_version: str
    to_version: str
    changed_fields: tuple[str, ...]
    reversible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierMigrationReport:
    observed_version: str
    current_version: str
    steps: tuple[PlatformFrontierMigrationStep, ...]
    migrated_payload: dict[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def migrate_platform_frontier_payload(payload: Mapping[str, Any]) -> PlatformFrontierMigrationReport:
    observed = str(payload.get("fixture_version", "unknown"))
    current = dict(payload)
    steps = []
    if observed != PLATFORM_FRONTIER_VERSION:
        body = {"migration_id": f"{observed}-to-current", "from_version": observed, "to_version": PLATFORM_FRONTIER_VERSION, "changed_fields": ("fixture_version", "migration_receipt"), "reversible": False}
        steps.append(PlatformFrontierMigrationStep(**body, content_address=content_hash(body)))
        current["fixture_version"] = PLATFORM_FRONTIER_VERSION
        current["migration_receipt"] = content_hash(body)
    accepted = current.get("fixture_version") == PLATFORM_FRONTIER_VERSION
    body = {"observed_version": observed, "current_version": PLATFORM_FRONTIER_VERSION, "steps": tuple(steps), "migrated_payload": current, "accepted": accepted}
    return PlatformFrontierMigrationReport(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierMigrationReport", "PlatformFrontierMigrationStep", "migrate_platform_frontier_payload"]
