"""Reviewer-oriented views over the service-release registry."""

from __future__ import annotations

from .service_release_contracts import (
    ServiceReleasePlane,
    ServiceReleaseSnapshot,
    ServiceReleaseView,
    ServiceReleaseViews,
    check,
)
from .serialization import content_hash


def _view(view_id: str, title: str, surface_ids: tuple[str, ...], columns: tuple[str, ...], rows) -> ServiceReleaseView:
    body = {"view_id": view_id, "title": title, "surface_ids": surface_ids,
            "columns": columns, "rows": tuple(rows), "accepted": True}
    return ServiceReleaseView(
        **body, content_address=content_hash(body, prefix="service-release-view")
    )


def build_service_release_views(snapshot: ServiceReleaseSnapshot) -> ServiceReleaseViews:
    """Build five complementary tables without exposing source payloads."""

    surface_ids = tuple(item.surface_id for item in snapshot.surfaces)
    surfaces = _view(
        "surface-matrix", "Service surface matrix", surface_ids,
        ("surface_id", "category", "dependency_order", "row_count", "artifact_count", "accepted"),
        ({"surface_id": item.surface_id, "category": item.category,
          "dependency_order": item.dependency_order, "row_count": item.row_count,
          "artifact_count": item.artifact_count, "accepted": item.accepted}
         for item in snapshot.surfaces),
    )
    artifacts = _view(
        "artifact-matrix", "Exact-byte artifact matrix", surface_ids,
        ("artifact_id", "surface_id", "relative_path", "media_type", "byte_count", "line_count"),
        ({"artifact_id": item.artifact_id, "surface_id": item.surface_id,
          "relative_path": item.relative_path, "media_type": item.media_type,
          "byte_count": item.byte_count, "line_count": item.line_count}
         for item in snapshot.artifacts),
    )
    gates = _view(
        "gate-matrix", "Promotion gate matrix", surface_ids,
        ("gate_id", "surface_id", "gate_type", "passed"),
        ({"gate_id": item.gate_id, "surface_id": item.surface_id,
          "gate_type": item.gate_type, "passed": item.passed}
         for item in snapshot.gates),
    )
    summary = _view(
        "promotion-summary", "Promotion summary", surface_ids,
        ("surface_id", "passed_gates", "total_gates", "accepted"),
        ({"surface_id": item.surface_id,
          "passed_gates": sum(gate.passed for gate in snapshot.gates if gate.surface_id == item.surface_id),
          "total_gates": sum(gate.surface_id == item.surface_id for gate in snapshot.gates),
          "accepted": item.accepted}
         for item in snapshot.surfaces),
    )
    dependency = _view(
        "dependency-order", "Dependency order", surface_ids,
        ("dependency_id", "source_surface_id", "target_surface_id", "relation"),
        ({"dependency_id": item.dependency_id, "source_surface_id": item.source_surface_id,
          "target_surface_id": item.target_surface_id, "relation": item.relation}
         for item in snapshot.dependencies),
    )
    values = (surfaces, artifacts, gates, summary, dependency)
    accepted = snapshot.accepted and all(item.accepted for item in values)
    body = {"bundle_id": snapshot.bundle_id, "views": values, "accepted": accepted}
    return ServiceReleaseViews(
        snapshot.bundle_id, values, accepted,
        content_hash(body, prefix="service-release-views"),
    )


def audit_service_release_views(views: ServiceReleaseViews, snapshot: ServiceReleaseSnapshot) -> tuple:
    """Check view identities, row closure, and public acceptance."""

    expected = {"surface-matrix": len(snapshot.surfaces), "artifact-matrix": len(snapshot.artifacts),
                "gate-matrix": len(snapshot.gates), "promotion-summary": len(snapshot.surfaces),
                "dependency-order": len(snapshot.dependencies)}
    return tuple(
        check(
            f"views:{item.view_id}", ServiceReleasePlane.RUNTIME,
            item.accepted and len(item.rows) == expected.get(item.view_id, -1),
            len(item.rows), expected.get(item.view_id),
            f"{item.view_id} closes its source row denominator",
        )
        for item in views.views
    ) + (
        check("views:count", ServiceReleasePlane.RUNTIME, len(views.views) == 5,
              len(views.views), 5, "all reviewer views are present"),
        check("views:accepted", ServiceReleasePlane.RUNTIME, views.accepted,
              views.accepted, True, "review views follow release acceptance"),
    )


__all__ = ["audit_service_release_views", "build_service_release_views"]
