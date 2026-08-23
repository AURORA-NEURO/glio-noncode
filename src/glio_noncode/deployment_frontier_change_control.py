"""Change-control receipt for deployment contract evolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DEPLOYMENT_FRONTIER_VERSION
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierChangeControl:
    change_id: str
    from_version: str
    to_version: str
    changed_surfaces: tuple[str, ...]
    migration_required: bool
    review_required: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_deployment_frontier_change_control() -> DeploymentFrontierChangeControl:
    body = {"change_id": "deployment-frontier-d16-c13-c16", "from_version": DEPLOYMENT_FRONTIER_VERSION, "to_version": DEPLOYMENT_FRONTIER_VERSION, "changed_surfaces": ("policy", "bundle", "federation", "release"), "migration_required": False, "review_required": True, "accepted": True}
    return DeploymentFrontierChangeControl(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierChangeControl", "default_deployment_frontier_change_control"]
