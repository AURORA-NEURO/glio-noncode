"""Certification checks for the service-release registry."""

from __future__ import annotations

from .service_release_contracts import (
    SERVICE_RELEASE_ARTIFACT_COUNT,
    SERVICE_RELEASE_DEPENDENCY_COUNT,
    SERVICE_RELEASE_GATE_COUNT,
    SERVICE_RELEASE_SURFACE_COUNT,
    ServiceReleaseCertification,
    ServiceReleasePlane,
    ServiceReleaseSnapshot,
    check,
)
from .service_release_support import forbidden_keys
from .serialization import content_hash, jsonable


def certify_service_release(snapshot: ServiceReleaseSnapshot) -> ServiceReleaseCertification:
    """Run six independent checks for each registered surface."""

    checks = []
    gates_by_surface = {
        surface_id: tuple(item for item in snapshot.gates if item.surface_id == surface_id)
        for surface_id in (item.surface_id for item in snapshot.surfaces)
    }
    artifacts_by_surface = {
        surface_id: tuple(item for item in snapshot.artifacts if item.surface_id == surface_id)
        for surface_id in (item.surface_id for item in snapshot.surfaces)
    }
    for surface in snapshot.surfaces:
        gates = gates_by_surface[surface.surface_id]
        artifacts = artifacts_by_surface[surface.surface_id]
        checks.extend(
            (
                check(
                    f"certification:{surface.surface_id}:accepted",
                    ServiceReleasePlane.CERTIFICATION,
                    surface.accepted,
                    surface.accepted,
                    True,
                    "surface source is accepted",
                ),
                check(
                    f"certification:{surface.surface_id}:source-address",
                    ServiceReleasePlane.CERTIFICATION,
                    bool(surface.source_address),
                    surface.source_address,
                    "non-empty",
                    "surface retains an immutable source address",
                ),
                check(
                    f"certification:{surface.surface_id}:row-count",
                    ServiceReleasePlane.CERTIFICATION,
                    surface.row_count > 0,
                    surface.row_count,
                    ">0",
                    "surface exposes a non-empty public denominator",
                ),
                check(
                    f"certification:{surface.surface_id}:artifact-count",
                    ServiceReleasePlane.CERTIFICATION,
                    len(artifacts) == surface.artifact_count,
                    len(artifacts),
                    surface.artifact_count,
                    "surface artifact contribution matches its declaration",
                ),
                check(
                    f"certification:{surface.surface_id}:gate-partition",
                    ServiceReleasePlane.CERTIFICATION,
                    len(gates) == 4 and all(item.passed for item in gates),
                    {"count": len(gates), "passed": sum(item.passed for item in gates)},
                    {"count": 4, "passed": 4},
                    "all surface promotion gates pass",
                ),
                check(
                    f"certification:{surface.surface_id}:public-address",
                    ServiceReleasePlane.BOUNDARY,
                    bool(surface.service_address) and not forbidden_keys(jsonable(surface)),
                    surface.service_address,
                    "public content address",
                    "surface projection is public and addressed",
                ),
            )
        )
    checks.extend(
        (
            check(
                "certification:registry-surface-count",
                ServiceReleasePlane.CERTIFICATION,
                len(snapshot.surfaces) == SERVICE_RELEASE_SURFACE_COUNT,
                len(snapshot.surfaces),
                SERVICE_RELEASE_SURFACE_COUNT,
                "registry contains all service surface domains",
            ),
            check(
                "certification:registry-artifact-count",
                ServiceReleasePlane.CERTIFICATION,
                len(snapshot.artifacts) == SERVICE_RELEASE_ARTIFACT_COUNT,
                len(snapshot.artifacts),
                SERVICE_RELEASE_ARTIFACT_COUNT,
                "registry contains all release artifacts",
            ),
            check(
                "certification:registry-dependency-count",
                ServiceReleasePlane.CERTIFICATION,
                len(snapshot.dependencies) == SERVICE_RELEASE_DEPENDENCY_COUNT,
                len(snapshot.dependencies),
                SERVICE_RELEASE_DEPENDENCY_COUNT,
                "registry contains the complete dependency matrix",
            ),
            check(
                "certification:registry-gate-count",
                ServiceReleasePlane.CERTIFICATION,
                len(snapshot.gates) == SERVICE_RELEASE_GATE_COUNT,
                len(snapshot.gates),
                SERVICE_RELEASE_GATE_COUNT,
                "registry contains every surface gate",
            ),
            check(
                "certification:registry-public-boundary",
                ServiceReleasePlane.BOUNDARY,
                not forbidden_keys(jsonable(snapshot)) and snapshot.accepted,
                snapshot.accepted,
                True,
                "complete registry is an accepted public projection",
            ),
        )
    )
    accepted = all(item.passed for item in checks) and snapshot.accepted
    body = {"bundle_id": snapshot.bundle_id, "checks": checks, "accepted": accepted}
    return ServiceReleaseCertification(
        snapshot.bundle_id,
        tuple(checks),
        accepted,
        content_hash(body, prefix="service-release-certification"),
    )


def audit_service_release_certification(
    certification: ServiceReleaseCertification,
    snapshot: ServiceReleaseSnapshot,
) -> tuple:
    """Return independent certification closure checks."""

    return (
        check(
            "certification-audit:address",
            ServiceReleasePlane.CERTIFICATION,
            bool(certification.content_address),
            certification.content_address,
            "non-empty",
            "certification report is addressed",
        ),
        check(
            "certification-audit:coverage",
            ServiceReleasePlane.CERTIFICATION,
            certification.coverage_percent == 100.0 if snapshot.accepted else certification.coverage_percent < 100.0,
            certification.coverage_percent,
            100.0 if snapshot.accepted else "<100",
            "certification coverage follows registry acceptance",
        ),
        check(
            "certification-audit:accepted",
            ServiceReleasePlane.CERTIFICATION,
            certification.accepted == snapshot.accepted,
            certification.accepted,
            snapshot.accepted,
            "certification acceptance follows snapshot acceptance",
        ),
    )


__all__ = ["audit_service_release_certification", "certify_service_release"]
