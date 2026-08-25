"""Build the immutable aggregate service-release registry.

This module is deliberately a projection builder.  It consumes the accepted
service snapshot, creates a small dependency-ordered registry of the public
surfaces, and never reaches into a case store or a mutable runtime object.
Every row and exact-byte artifact receives its own content address.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .service_release_contracts import (
    SERVICE_RELEASE_ARTIFACT_COUNT,
    SERVICE_RELEASE_DEPENDENCY_COUNT,
    SERVICE_RELEASE_GATE_COUNT,
    SERVICE_RELEASE_GATE_TYPES,
    SERVICE_RELEASE_SURFACE_COUNT,
    SERVICE_RELEASE_SURFACE_IDS,
    ServiceReleaseArtifact,
    ServiceReleaseDependency,
    ServiceReleaseGate,
    ServiceReleaseSnapshot,
    ServiceReleaseSurface,
)
from .service_release_support import (
    artifact_address,
    canonical_payload,
    csv_payload,
    forbidden_keys,
    line_count,
    markdown_payload,
    safe_relative_path,
)
from .service_surface import (
    ServiceSurfaceSnapshot,
    service_operational_projection,
    service_surface_status,
)


def _addressed(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


def _surface_values(snapshot: ServiceSurfaceSnapshot) -> tuple[dict[str, Any], ...]:
    """Return one stable source description for every registered surface."""

    status = service_surface_status(snapshot)
    boundary = status["public_boundary"]
    release = snapshot.program_release
    return (
        {
            "surface_id": "capability-certification",
            "category": "certification",
            "source_address": snapshot.capability_report.content_address,
            "service_address": snapshot.capability_report.content_address,
            "row_count": len(snapshot.capability_report.certificates),
            "artifact_count": 2,
            "accepted": snapshot.capability_report.accepted,
        },
        {
            "surface_id": "architecture-program",
            "category": "runtime",
            "source_address": snapshot.program_runtime.content_address,
            "service_address": snapshot.program_runtime.content_address,
            "row_count": len(snapshot.program_runtime.report.receipts),
            "artifact_count": 2,
            "accepted": snapshot.program_runtime.accepted,
        },
        {
            "surface_id": "operational",
            "category": "operations",
            "source_address": snapshot.operational_trace.content_address,
            "service_address": snapshot.operational_trace.content_address,
            "row_count": len(snapshot.operational_trace.artifacts),
            "artifact_count": 1,
            "accepted": snapshot.operational_trace.accepted,
        },
        {
            "surface_id": "program-release",
            "category": "release",
            "source_address": release.content_address,
            "service_address": release.content_address,
            "row_count": len(release.domains),
            "artifact_count": 4,
            "accepted": release.accepted,
        },
        {
            "surface_id": "service-status",
            "category": "health",
            "source_address": snapshot.content_address,
            "service_address": _addressed(status, "service-release-status"),
            "row_count": 1,
            "artifact_count": 1,
            "accepted": snapshot.accepted,
        },
        {
            "surface_id": "public-boundary",
            "category": "boundary",
            "source_address": snapshot.content_address,
            "service_address": _addressed(boundary, "service-release-boundary"),
            "row_count": 1,
            "artifact_count": 3,
            "accepted": bool(boundary.get("safe")) and snapshot.accepted,
        },
    )


def build_service_release_surfaces(snapshot: ServiceSurfaceSnapshot) -> tuple[ServiceReleaseSurface, ...]:
    """Materialize the six surface registry rows in dependency order."""

    rows = _surface_values(snapshot)
    if tuple(row["surface_id"] for row in rows) != SERVICE_RELEASE_SURFACE_IDS:
        raise ValidationError("service release surface order is not closed")
    result: list[ServiceReleaseSurface] = []
    for ordinal, row in enumerate(rows, start=1):
        body = {"dependency_order": ordinal, **row}
        result.append(
            ServiceReleaseSurface(
                **body,
                content_address=_addressed(body, "service-release-surface"),
            )
        )
    return tuple(result)


def _artifact_values(snapshot: ServiceSurfaceSnapshot) -> tuple[tuple[str, str, str, Any], ...]:
    """Return exact export definitions before byte addressing."""

    status = service_surface_status(snapshot)
    capability = snapshot.capability_report.to_dict()
    program = snapshot.program_runtime.to_dict()
    operational = service_operational_projection(snapshot)
    release = snapshot.program_release.to_dict()
    release_domains = [item.to_dict() for item in snapshot.program_release.domains]
    release_gates = [item.to_dict() for item in snapshot.program_release.gates]
    release_dependencies = [item.to_dict() for item in snapshot.program_release.dependencies]
    boundary = status["public_boundary"]
    rows = [
        ("status-json", "service-status", "surfaces/status.json", "application/json", status),
        ("capability-report-json", "capability-certification", "surfaces/capabilities.json", "application/json", capability),
        ("capability-summary-csv", "capability-certification", "surfaces/capabilities.csv", "text/csv", ({"capability_id": item.capability_id, "domain_id": item.domain_id, "state": item.state.value} for item in snapshot.capability_report.certificates)),
        ("program-runtime-json", "architecture-program", "surfaces/program-runtime.json", "application/json", program),
        ("program-summary-csv", "architecture-program", "surfaces/program.csv", "text/csv", [item.to_dict() for item in snapshot.program_runtime.report.receipts]),
        ("operational-json", "operational", "surfaces/operational.json", "application/json", operational),
        ("program-release-json", "program-release", "surfaces/program-release.json", "application/json", release),
        ("program-release-domains-csv", "program-release", "surfaces/program-release-domains.csv", "text/csv", release_domains),
        ("program-release-gates-csv", "program-release", "surfaces/program-release-gates.csv", "text/csv", release_gates),
        ("program-release-dependencies-csv", "program-release", "surfaces/program-release-dependencies.csv", "text/csv", release_dependencies),
        ("boundary-json", "public-boundary", "surfaces/boundary.json", "application/json", boundary),
        ("boundary-summary-csv", "public-boundary", "surfaces/boundary.csv", "text/csv", ({"surface": key, "value": value} for key, value in sorted(boundary.items()))),
        ("release-review-markdown", "public-boundary", "review/service-release.md", "text/markdown", ("Service release registry", ({"surface_id": item.surface_id, "category": item.category, "accepted": item.accepted, "source_address": item.source_address} for item in build_service_release_surfaces(snapshot)))),
    ]
    return tuple(rows)


def _payload(value: Any, media_type: str) -> bytes:
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        return markdown_payload(value[0], value[1])
    if media_type == "text/csv":
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
            return csv_payload(value)
        return csv_payload((value,))
    if media_type == "text/markdown":
        title, rows = value
        return markdown_payload(title, rows)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict, list, tuple)):
        return csv_payload(value)
    if isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)):
        return canonical_payload(value)
    return canonical_payload(value)


def build_service_release_artifacts(
    snapshot: ServiceSurfaceSnapshot,
    surfaces: tuple[ServiceReleaseSurface, ...] | None = None,
) -> tuple[ServiceReleaseArtifact, ...]:
    """Build the thirteen exact-byte artifacts in stable path order."""

    selected = surfaces or build_service_release_surfaces(snapshot)
    surface_map = {item.surface_id: item for item in selected}
    artifacts: list[ServiceReleaseArtifact] = []
    for artifact_id, surface_id, relative_path, media_type, value in _artifact_values(snapshot):
        path = safe_relative_path(relative_path)
        payload = _payload(value, media_type)
        source = surface_map[surface_id]
        body = {
            "artifact_ref": f"service:{artifact_id}",
            "artifact_id": artifact_id,
            "surface_id": surface_id,
            "relative_path": path,
            "media_type": media_type,
            "source_address": source.content_address,
            "byte_count": len(payload),
            "line_count": line_count(payload),
        }
        artifacts.append(
            ServiceReleaseArtifact(
                **body,
                content_address=artifact_address(payload),
            )
        )
    result = tuple(artifacts)
    if len(result) != SERVICE_RELEASE_ARTIFACT_COUNT:
        raise ValidationError("service release artifact denominator is not closed")
    if len({item.relative_path for item in result}) != len(result):
        raise ValidationError("service release artifact paths must be unique")
    return result


def service_release_artifact_payloads(snapshot: ServiceSurfaceSnapshot) -> dict[str, bytes]:
    """Rebuild the exact bytes behind every artifact in a release packet."""

    return {
        artifact_id: _payload(value, media_type)
        for artifact_id, _surface_id, _path, media_type, value in _artifact_values(snapshot)
    }


def build_service_release_dependencies(
    surfaces: tuple[ServiceReleaseSurface, ...],
) -> tuple[ServiceReleaseDependency, ...]:
    """Build the complete forward dependency matrix for surface promotion."""

    values: list[ServiceReleaseDependency] = []
    for source in surfaces:
        for target in surfaces:
            if source.dependency_order >= target.dependency_order:
                continue
            body = {
                "dependency_id": f"dependency:{source.surface_id}:{target.surface_id}",
                "source_surface_id": source.surface_id,
                "target_surface_id": target.surface_id,
                "relation": "surface_precedes",
                "source_order": source.dependency_order,
                "target_order": target.dependency_order,
            }
            values.append(
                ServiceReleaseDependency(
                    **body,
                    content_address=_addressed(body, "service-release-dependency"),
                )
            )
    result = tuple(values)
    if len(result) != SERVICE_RELEASE_DEPENDENCY_COUNT:
        raise ValidationError("service release dependency denominator is not closed")
    return result


def _gate_value(surface: ServiceReleaseSurface, gate_type: str) -> tuple[Any, Any, bool]:
    if gate_type == "source_accepted":
        return surface.accepted, True, surface.accepted is True
    if gate_type == "address_present":
        return surface.source_address, "non-empty", bool(surface.source_address)
    if gate_type == "row_denominator":
        return surface.row_count, ">0", surface.row_count > 0
    return surface.service_address, "public-address", bool(surface.service_address)


def build_service_release_gates(
    surfaces: tuple[ServiceReleaseSurface, ...],
) -> tuple[ServiceReleaseGate, ...]:
    """Evaluate four independent promotion gates for every surface."""

    values: list[ServiceReleaseGate] = []
    for surface in surfaces:
        for gate_type in SERVICE_RELEASE_GATE_TYPES:
            observed, expected, passed = _gate_value(surface, gate_type)
            body = {
                "gate_id": f"gate:{surface.surface_id}:{gate_type}",
                "surface_id": surface.surface_id,
                "gate_type": gate_type,
                "passed": passed,
                "observed": observed,
                "expected": expected,
                "source_address": surface.content_address,
            }
            values.append(
                ServiceReleaseGate(
                    **body,
                    content_address=_addressed(body, "service-release-gate"),
                )
            )
    result = tuple(values)
    if len(result) != SERVICE_RELEASE_GATE_COUNT:
        raise ValidationError("service release gate denominator is not closed")
    return result


def build_service_release_snapshot(
    source_snapshot: ServiceSurfaceSnapshot | None = None,
    *,
    bundle_id: str = "glio-noncode-service-release",
) -> ServiceReleaseSnapshot:
    """Build the accepted public registry from one cached service snapshot."""

    require_non_empty(bundle_id, "bundle_id")
    source = source_snapshot or __import__(
        "glio_noncode.service_surface", fromlist=["build_service_surface_snapshot"]
    ).build_service_surface_snapshot()
    surfaces = build_service_release_surfaces(source)
    artifacts = build_service_release_artifacts(source, surfaces)
    dependencies = build_service_release_dependencies(surfaces)
    gates = build_service_release_gates(surfaces)
    body = {
        "bundle_id": bundle_id,
        "service_address": source.content_address,
        "source_surface_address": source.content_address,
        "surfaces": surfaces,
        "artifacts": artifacts,
        "dependencies": dependencies,
        "gates": gates,
    }
    accepted = (
        source.accepted
        and len(surfaces) == SERVICE_RELEASE_SURFACE_COUNT
        and tuple(item.surface_id for item in surfaces) == SERVICE_RELEASE_SURFACE_IDS
        and len(artifacts) == SERVICE_RELEASE_ARTIFACT_COUNT
        and len(dependencies) == SERVICE_RELEASE_DEPENDENCY_COUNT
        and len(gates) == SERVICE_RELEASE_GATE_COUNT
        and all(item.accepted for item in surfaces)
        and all(item.passed for item in gates)
        and not forbidden_keys(jsonable(body))
    )
    return ServiceReleaseSnapshot(
        bundle_id=bundle_id,
        service_address=source.content_address,
        source_surface_address=source.content_address,
        surfaces=surfaces,
        artifacts=artifacts,
        dependencies=dependencies,
        gates=gates,
        accepted=accepted,
        content_address=_addressed(body | {"accepted": accepted}, "service-release"),
    )


def service_release_snapshot_counts(snapshot: ServiceReleaseSnapshot) -> dict[str, int | bool]:
    """Return conserved registry denominators for status and reconciliation."""

    return {
        "surface_count": len(snapshot.surfaces),
        "artifact_count": len(snapshot.artifacts),
        "dependency_count": len(snapshot.dependencies),
        "gate_count": len(snapshot.gates),
        "accepted_surface_count": sum(item.accepted for item in snapshot.surfaces),
        "passed_gate_count": sum(item.passed for item in snapshot.gates),
        "accepted": snapshot.accepted,
    }


def service_release_snapshot_rows(snapshot: ServiceReleaseSnapshot) -> dict[str, list[dict[str, Any]]]:
    """Return public rows for query and export modules."""

    return {
        "surfaces": [item.to_dict() for item in snapshot.surfaces],
        "artifacts": [item.to_dict() for item in snapshot.artifacts],
        "dependencies": [item.to_dict() for item in snapshot.dependencies],
        "gates": [item.to_dict() for item in snapshot.gates],
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("SERVICE_RELEASE")
    or name.startswith("ServiceRelease")
    or name.startswith("build_service_release")
    or name.startswith("service_release_snapshot")
    or name == "service_release_artifact_payloads"
]
