"""Public access manifest for aggregate platform projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PLATFORM_FRONTIER_BOUNDARY, PlatformFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierAccessSurface:
    surface_id: str
    media_type: str
    path_hint: str
    controls_visible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierAccessManifest:
    fixture_id: str
    boundary: str
    surfaces: tuple[PlatformFrontierAccessSurface, ...]
    private_data: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"surface_ids": [item.surface_id for item in self.surfaces]}


def build_platform_frontier_access_manifest(fixture: PlatformFrontierFixture) -> PlatformFrontierAccessManifest:
    specs = (("fixture-json", "application/json", "aggregate/platform-fixture.json"), ("evaluation-json", "application/json", "aggregate/platform-evaluation.json"), ("review-csv", "text/csv", "aggregate/platform-review.csv"), ("metrics-csv", "text/csv", "aggregate/platform-metrics.csv"), ("release-json", "application/json", "aggregate/platform-release.json"), ("trace-json", "application/json", "aggregate/platform-trace.json"))
    surfaces = []
    for surface_id, media_type, path_hint in specs:
        body = {"surface_id": surface_id, "media_type": media_type, "path_hint": path_hint, "controls_visible": True}
        surfaces.append(PlatformFrontierAccessSurface(**body, content_address=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "boundary": PLATFORM_FRONTIER_BOUNDARY, "surfaces": tuple(surfaces), "private_data": False, "accepted": fixture.evidence_boundary == PLATFORM_FRONTIER_BOUNDARY and len(surfaces) == 6}
    return PlatformFrontierAccessManifest(**body, content_address=content_hash(body))


def audit_platform_frontier_access(manifest: PlatformFrontierAccessManifest) -> tuple[str, ...]:
    issues = []
    if manifest.boundary != PLATFORM_FRONTIER_BOUNDARY:
        issues.append("boundary_mismatch")
    if manifest.private_data:
        issues.append("private_data")
    if any(not item.controls_visible for item in manifest.surfaces):
        issues.append("controls_hidden")
    return tuple(issues)


__all__ = ["PlatformFrontierAccessManifest", "PlatformFrontierAccessSurface", "audit_platform_frontier_access", "build_platform_frontier_access_manifest"]
