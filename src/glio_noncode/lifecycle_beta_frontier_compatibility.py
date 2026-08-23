"""Version and schema compatibility checks for exported receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LIFECYCLE_BETA_FRONTIER_VERSION, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_schema import LifecycleBetaFrontierSchema, validate_lifecycle_beta_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierCompatibilityReport:
    fixture_version: str
    schema_id: str
    supported_versions: tuple[str, ...]
    schema_valid: bool
    version_supported: bool
    accepted: bool
    blockers: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_lifecycle_beta_frontier_compatibility(fixture: LifecycleBetaFrontierFixture, schema: LifecycleBetaFrontierSchema) -> LifecycleBetaFrontierCompatibilityReport:
    supported = (LIFECYCLE_BETA_FRONTIER_VERSION,)
    schema_valid = validate_lifecycle_beta_frontier_schema(schema)
    version_supported = fixture.fixture_version in supported
    blockers = tuple(item for item, failed in (("schema_invalid", not schema_valid), ("fixture_version_unsupported", not version_supported)) if failed)
    body = {"fixture_version": fixture.fixture_version, "schema_id": schema.schema_id, "supported_versions": supported, "schema_valid": schema_valid, "version_supported": version_supported, "accepted": not blockers, "blockers": blockers}
    return LifecycleBetaFrontierCompatibilityReport(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierCompatibilityReport", "evaluate_lifecycle_beta_frontier_compatibility"]
