"""Version compatibility and metadata migration receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import VALIDATION_RELEASE_FRONTIER_VERSION


@dataclass(frozen=True, slots=True)
class ValidationReleaseVersionReceipt:
    version: str
    compatible: bool
    migration_required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def inspect_validation_release_version(version: str) -> ValidationReleaseVersionReceipt:
    body = {"version": version, "compatible": version == VALIDATION_RELEASE_FRONTIER_VERSION, "migration_required": version != VALIDATION_RELEASE_FRONTIER_VERSION}
    return ValidationReleaseVersionReceipt(**body, content_address=content_hash(body))


def migrate_validation_release_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    result = dict(metadata)
    result["validation_release_version"] = VALIDATION_RELEASE_FRONTIER_VERSION
    result["migration_address"] = content_hash(result)
    return result


__all__ = ["ValidationReleaseVersionReceipt", "inspect_validation_release_version", "migrate_validation_release_metadata"]
