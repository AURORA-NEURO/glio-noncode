"""Public access manifest and boundary checks for the lifecycle fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import (
    LIFECYCLE_BETA_FRONTIER_BOUNDARY,
    LifecycleBetaFrontierFixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAccessSurface:
    """One documented public surface with its permitted retrieval mode."""

    surface_id: str
    media_type: str
    path_hint: str
    boundary: str
    supports_controls: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("surface_id", "media_type", "path_hint", "boundary"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAccessManifest:
    """Stable access contract for consumers of aggregate-only outputs."""

    fixture_id: str
    boundary: str
    surfaces: tuple[LifecycleBetaFrontierAccessSurface, ...]
    controls_visible: bool
    patient_level_data: bool
    accepted: bool
    content_address: str

    @property
    def surface_ids(self) -> tuple[str, ...]:
        return tuple(item.surface_id for item in self.surfaces)

    def surface(self, surface_id: str) -> LifecycleBetaFrontierAccessSurface:
        require_non_empty(surface_id, "surface_id")
        return next(item for item in self.surfaces if item.surface_id == surface_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"surface_ids": list(self.surface_ids)}


def build_lifecycle_beta_frontier_access_manifest(
    fixture: LifecycleBetaFrontierFixture,
) -> LifecycleBetaFrontierAccessManifest:
    """Describe JSON, CSV, trace, and review surfaces without widening scope."""

    surface_specs = (
        ("fixture-json", "application/json", "aggregate/fixture.json", True),
        ("evaluation-json", "application/json", "aggregate/evaluation.json", True),
        ("review-csv", "text/csv", "aggregate/review.csv", True),
        ("metrics-csv", "text/csv", "aggregate/metrics.csv", False),
        ("trace-json", "application/json", "aggregate/trace.json", False),
        ("release-json", "application/json", "aggregate/release.json", False),
    )
    surfaces = []
    for surface_id, media_type, path_hint, supports_controls in surface_specs:
        body = {
            "surface_id": surface_id,
            "media_type": media_type,
            "path_hint": path_hint,
            "boundary": LIFECYCLE_BETA_FRONTIER_BOUNDARY,
            "supports_controls": supports_controls,
        }
        surfaces.append(LifecycleBetaFrontierAccessSurface(**body, content_address=content_hash(body)))
    accepted = (
        fixture.evidence_boundary == LIFECYCLE_BETA_FRONTIER_BOUNDARY
        and len(surfaces) == 6
        and all(item.boundary == LIFECYCLE_BETA_FRONTIER_BOUNDARY for item in surfaces)
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "boundary": LIFECYCLE_BETA_FRONTIER_BOUNDARY,
        "surfaces": tuple(surfaces),
        "controls_visible": True,
        "patient_level_data": False,
        "accepted": accepted,
    }
    return LifecycleBetaFrontierAccessManifest(**body, content_address=content_hash(body))


def audit_lifecycle_beta_frontier_access(manifest: LifecycleBetaFrontierAccessManifest) -> tuple[str, ...]:
    """Return explicit access violations; an empty tuple is an accepted audit."""

    issues: list[str] = []
    if manifest.boundary != LIFECYCLE_BETA_FRONTIER_BOUNDARY:
        issues.append("boundary-mismatch")
    if manifest.patient_level_data:
        issues.append("patient-level-data")
    if not manifest.controls_visible:
        issues.append("controls-hidden")
    if len(set(manifest.surface_ids)) != len(manifest.surface_ids):
        issues.append("duplicate-surface-id")
    return tuple(issues)


__all__ = [
    "LifecycleBetaFrontierAccessManifest",
    "LifecycleBetaFrontierAccessSurface",
    "audit_lifecycle_beta_frontier_access",
    "build_lifecycle_beta_frontier_access_manifest",
]
