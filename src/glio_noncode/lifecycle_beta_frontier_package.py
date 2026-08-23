"""Package manifest joining every lifecycle beta publication surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_bundle import LifecycleBetaFrontierReleaseBundle
from .lifecycle_beta_frontier_depth import LifecycleBetaFrontierDepthAudit
from .lifecycle_beta_frontier_handoff import LifecycleBetaFrontierHandoff
from .lifecycle_beta_frontier_validation_matrix import LifecycleBetaFrontierValidationMatrix
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierPackageManifest:
    package_id: str
    surface_addresses: dict[str, str]
    surface_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_package_manifest(bundle: LifecycleBetaFrontierReleaseBundle, depth: LifecycleBetaFrontierDepthAudit, handoff: LifecycleBetaFrontierHandoff, matrix: LifecycleBetaFrontierValidationMatrix) -> LifecycleBetaFrontierPackageManifest:
    addresses = {"bundle": bundle.content_address, "depth": depth.content_address, "handoff": handoff.content_address, "validation_matrix": matrix.content_address}
    body = {"package_id": "lifecycle-beta-frontier-package", "surface_addresses": addresses, "surface_count": len(addresses), "accepted": bundle.publishable and depth.accepted and handoff.accepted and matrix.accepted}
    return LifecycleBetaFrontierPackageManifest(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierPackageManifest", "build_lifecycle_beta_frontier_package_manifest"]
