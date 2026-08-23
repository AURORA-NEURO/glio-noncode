"""Public access manifest for aggregate control frontier outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import CONTROL_FRONTIER_BOUNDARY, ControlFrontierFixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ControlFrontierAccessSurface:
    surface_id: str
    media_type: str
    path_hint: str
    boundary: str
    controls_visible: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("surface_id", "media_type", "path_hint", "boundary"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierAccessManifest:
    fixture_id: str
    boundary: str
    surfaces: tuple[ControlFrontierAccessSurface, ...]
    patient_level_data: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"surface_ids": [item.surface_id for item in self.surfaces]}


def build_control_frontier_access_manifest(fixture: ControlFrontierFixture) -> ControlFrontierAccessManifest:
    specs = (("fixture-json", "application/json", "aggregate/fixture.json", True), ("evaluation-json", "application/json", "aggregate/evaluation.json", True), ("review-csv", "text/csv", "aggregate/review.csv", True), ("metrics-csv", "text/csv", "aggregate/metrics.csv", True), ("release-json", "application/json", "aggregate/release.json", True), ("trace-json", "application/json", "aggregate/trace.json", True))
    surfaces = []
    for surface_id, media_type, path_hint, controls_visible in specs:
        body = {"surface_id": surface_id, "media_type": media_type, "path_hint": path_hint, "boundary": CONTROL_FRONTIER_BOUNDARY, "controls_visible": controls_visible}
        surfaces.append(ControlFrontierAccessSurface(**body, content_address=content_hash(body)))
    accepted = fixture.evidence_boundary == CONTROL_FRONTIER_BOUNDARY and len(surfaces) == 6 and all(item.controls_visible for item in surfaces)
    body = {"fixture_id": fixture.fixture_id, "boundary": CONTROL_FRONTIER_BOUNDARY, "surfaces": tuple(surfaces), "patient_level_data": False, "accepted": accepted}
    return ControlFrontierAccessManifest(**body, content_address=content_hash(body))


def audit_control_frontier_access(manifest: ControlFrontierAccessManifest) -> tuple[str, ...]:
    issues = []
    if manifest.boundary != CONTROL_FRONTIER_BOUNDARY:
        issues.append("boundary_mismatch")
    if manifest.patient_level_data:
        issues.append("patient_level_data")
    if any(not item.controls_visible for item in manifest.surfaces):
        issues.append("controls_hidden")
    return tuple(issues)


__all__ = ["ControlFrontierAccessManifest", "ControlFrontierAccessSurface", "audit_control_frontier_access", "build_control_frontier_access_manifest"]
