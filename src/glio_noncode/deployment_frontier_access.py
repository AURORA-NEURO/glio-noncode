"""Access manifest for public aggregate deployment receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierFixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierAccessSurface:
    surface_id: str
    format: str
    scope: str
    public: bool
    patient_level: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierAccessManifest:
    surfaces: tuple[DeploymentFrontierAccessSurface, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_access_manifest(fixture: DeploymentFrontierFixture) -> DeploymentFrontierAccessManifest:
    rows = (
        ("fixture-json", "json", "aggregate fixture", True, False),
        ("review-csv", "csv", "review projection", True, False),
        ("runtime-json", "json", "runtime receipts", True, False),
    )
    surfaces = []
    for surface_id, format_name, scope, public, patient_level in rows:
        body = {"surface_id": surface_id, "format": format_name, "scope": scope, "public": public, "patient_level": patient_level}
        surfaces.append(DeploymentFrontierAccessSurface(**body, content_address=deployment_address(body)))
    return DeploymentFrontierAccessManifest(tuple(surfaces), all(item.public and not item.patient_level for item in surfaces), deployment_address(tuple(surfaces)))


def audit_deployment_frontier_access(manifest: DeploymentFrontierAccessManifest) -> tuple[str, ...]:
    return tuple(item.surface_id for item in manifest.surfaces if not item.public or item.patient_level)


__all__ = ["DeploymentFrontierAccessManifest", "DeploymentFrontierAccessSurface", "audit_deployment_frontier_access", "build_deployment_frontier_access_manifest"]
