"""Version receipt and migration boundary for deployment artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DEPLOYMENT_FRONTIER_VERSION
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierVersionReceipt:
    expected_version: str
    observed_version: str
    compatible: bool
    migration: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def inspect_deployment_frontier_version(observed_version: str) -> DeploymentFrontierVersionReceipt:
    compatible = observed_version == DEPLOYMENT_FRONTIER_VERSION
    body = {"expected_version": DEPLOYMENT_FRONTIER_VERSION, "observed_version": observed_version, "compatible": compatible, "migration": "none" if compatible else "review_required"}
    return DeploymentFrontierVersionReceipt(**body, content_address=deployment_address(body))


def migrate_deployment_frontier_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["deployment_frontier_version"] = DEPLOYMENT_FRONTIER_VERSION
    result["migration_address"] = deployment_address({"from": payload.get("deployment_frontier_version", "unknown"), "to": DEPLOYMENT_FRONTIER_VERSION})
    return result


__all__ = ["DeploymentFrontierVersionReceipt", "inspect_deployment_frontier_version", "migrate_deployment_frontier_metadata"]
