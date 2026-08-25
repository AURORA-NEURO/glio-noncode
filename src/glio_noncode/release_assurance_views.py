"""Reviewer views for whole-product release assurance."""

from __future__ import annotations

from .release_assurance_contracts import (
    RELEASE_ASSURANCE_VIEW_COUNT,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    ReleaseAssuranceView,
    ReleaseAssuranceViews,
    check,
)
from .serialization import content_hash


def _view(view_id: str, title: str, columns: tuple[str, ...], rows, domains: tuple[str, ...]) -> ReleaseAssuranceView:
    body = {
        "view_id": view_id,
        "title": title,
        "columns": columns,
        "rows": tuple(rows),
        "source_domain_ids": domains,
        "accepted": True,
    }
    return ReleaseAssuranceView(
        **body,
        content_address=content_hash(body, prefix="release-assurance-view"),
    )


def build_release_assurance_views(snapshot: ReleaseAssuranceSnapshot) -> ReleaseAssuranceViews:
    """Build readiness, check, evidence, and status tables."""

    domains = tuple(item.domain_id for item in snapshot.domains)
    readiness = _view(
        "readiness-matrix",
        "Whole-product readiness matrix",
        ("domain_id", "title", "denominator", "accepted_count", "readiness_percent", "accepted"),
        ({"domain_id": item.domain_id, "title": item.title,
          "denominator": item.denominator, "accepted_count": item.accepted_count,
          "readiness_percent": item.readiness_percent, "accepted": item.accepted}
         for item in snapshot.domains),
        domains,
    )
    checks = _view(
        "check-matrix",
        "Cross-plane check matrix",
        ("check_id", "domain_id", "plane", "passed", "detail"),
        ({"check_id": item.check_id, "domain_id": item.domain_id,
          "plane": item.plane, "passed": item.passed, "detail": item.detail}
         for item in snapshot.checks),
        domains,
    )
    evidence = _view(
        "evidence-matrix",
        "Evidence address matrix",
        ("link_id", "domain_id", "evidence_type", "role", "source_address", "accepted"),
        ({"link_id": item.link_id, "domain_id": item.domain_id,
          "evidence_type": item.evidence_type, "role": item.role,
          "source_address": item.source_address, "accepted": item.accepted}
         for item in snapshot.evidence),
        domains,
    )
    status = _view(
        "release-status",
        "Release status",
        ("bundle_id", "overall_percent", "check_count", "passed_check_count", "accepted"),
        ({"bundle_id": snapshot.bundle_id, "overall_percent": snapshot.overall_percent,
          "check_count": len(snapshot.checks), "passed_check_count": snapshot.passed_check_count,
          "accepted": snapshot.accepted},),
        domains,
    )
    values = (readiness, checks, evidence, status)
    accepted = snapshot.accepted and all(item.accepted for item in values)
    body = {"bundle_id": snapshot.bundle_id, "views": values, "accepted": accepted}
    return ReleaseAssuranceViews(
        snapshot.bundle_id,
        values,
        accepted,
        content_hash(body, prefix="release-assurance-views"),
    )


def audit_release_assurance_views(
    views: ReleaseAssuranceViews,
    snapshot: ReleaseAssuranceSnapshot,
) -> tuple:
    """Check view row closure and public acceptance."""

    expected = {
        "readiness-matrix": len(snapshot.domains),
        "check-matrix": len(snapshot.checks),
        "evidence-matrix": len(snapshot.evidence),
        "release-status": 1,
    }
    return tuple(
        check(
            f"views:{item.view_id}", "views", ReleaseAssurancePlane.RUNTIME,
            item.accepted and len(item.rows) == expected[item.view_id],
            len(item.rows), expected[item.view_id],
            f"{item.view_id} closes its source row denominator",
        )
        for item in views.views
    ) + (
        check("views:count", "views", ReleaseAssurancePlane.RUNTIME,
              len(views.views) == RELEASE_ASSURANCE_VIEW_COUNT, len(views.views),
              RELEASE_ASSURANCE_VIEW_COUNT, "all reviewer views are present"),
        check("views:accepted", "views", ReleaseAssurancePlane.RUNTIME,
              views.accepted, views.accepted, True, "views follow release acceptance"),
    )


__all__ = ["audit_release_assurance_views", "build_release_assurance_views"]
