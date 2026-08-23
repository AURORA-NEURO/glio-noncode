"""Compatibility checks for platform fixture versions and contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_adapters import PlatformFrontierAdapterRegistry
from .platform_frontier_contracts import PLATFORM_FRONTIER_VERSION
from .platform_frontier_schema import PlatformFrontierSchema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierCompatibilityReport:
    observed_version: str
    required_version: str
    adapter_count: int
    operation_count: int
    compatible: bool
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_compatibility(version: str, adapters: PlatformFrontierAdapterRegistry, schema: PlatformFrontierSchema) -> PlatformFrontierCompatibilityReport:
    issues = []
    if version != PLATFORM_FRONTIER_VERSION:
        issues.append("version_mismatch")
    if len(adapters.specs) != 4:
        issues.append("adapter_count")
    if len(schema.operation_fields) != 4:
        issues.append("schema_operation_count")
    body = {"observed_version": version, "required_version": PLATFORM_FRONTIER_VERSION, "adapter_count": len(adapters.specs), "operation_count": len(schema.operation_fields), "compatible": not issues, "issues": tuple(issues)}
    return PlatformFrontierCompatibilityReport(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierCompatibilityReport", "evaluate_platform_frontier_compatibility"]
