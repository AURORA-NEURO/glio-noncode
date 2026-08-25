"""Schema declaration and validation for service-release outputs."""

from __future__ import annotations

from typing import Any

from .service_release_contracts import (
    SERVICE_RELEASE_ARTIFACT_COUNT,
    SERVICE_RELEASE_DEPENDENCY_COUNT,
    SERVICE_RELEASE_GATE_COUNT,
    SERVICE_RELEASE_SCHEMA_VERSION,
    SERVICE_RELEASE_SURFACE_COUNT,
    ServiceReleasePlane,
    ServiceReleaseSnapshot,
    check,
)
from .service_release_support import forbidden_keys
from .serialization import content_hash


def service_release_schema() -> dict[str, Any]:
    """Return the machine-readable public contract for registry resources."""

    return {
        "version": SERVICE_RELEASE_SCHEMA_VERSION,
        "boundary": "public aggregate service surfaces only",
        "resources": {
            "surfaces": {"identity": "surface_id", "required": ["surface_id", "source_address", "accepted"]},
            "artifacts": {"identity": "artifact_ref", "required": ["artifact_ref", "relative_path", "content_address"]},
            "dependencies": {"identity": "dependency_id", "required": ["dependency_id", "source_surface_id", "target_surface_id"]},
            "gates": {"identity": "gate_id", "required": ["gate_id", "surface_id", "gate_type", "passed"]},
        },
        "denominators": {
            "surface_count": SERVICE_RELEASE_SURFACE_COUNT,
            "artifact_count": SERVICE_RELEASE_ARTIFACT_COUNT,
            "dependency_count": SERVICE_RELEASE_DEPENDENCY_COUNT,
            "gate_count": SERVICE_RELEASE_GATE_COUNT,
        },
        "public_boundary": {
            "forbidden_key_policy": "recursive-key-and-token-filter",
            "exact_byte_artifacts": True,
            "source_records": "aggregate-only",
        },
    }


def validate_service_release_schema(
    snapshot: ServiceReleaseSnapshot,
    schema: dict[str, Any] | None = None,
) -> tuple:
    """Validate required fields, denominators, and the recursive key policy."""

    selected = schema or service_release_schema()
    checks = [
        check("schema:version", ServiceReleasePlane.BOUNDARY,
              selected.get("version") == SERVICE_RELEASE_SCHEMA_VERSION,
              selected.get("version"), SERVICE_RELEASE_SCHEMA_VERSION,
              "schema version is current"),
        check("schema:surface-count", ServiceReleasePlane.BOUNDARY,
              len(snapshot.surfaces) == selected["denominators"]["surface_count"],
              len(snapshot.surfaces), selected["denominators"]["surface_count"],
              "surface denominator matches schema"),
        check("schema:artifact-count", ServiceReleasePlane.BOUNDARY,
              len(snapshot.artifacts) == selected["denominators"]["artifact_count"],
              len(snapshot.artifacts), selected["denominators"]["artifact_count"],
              "artifact denominator matches schema"),
        check("schema:dependency-count", ServiceReleasePlane.BOUNDARY,
              len(snapshot.dependencies) == selected["denominators"]["dependency_count"],
              len(snapshot.dependencies), selected["denominators"]["dependency_count"],
              "dependency denominator matches schema"),
        check("schema:gate-count", ServiceReleasePlane.BOUNDARY,
              len(snapshot.gates) == selected["denominators"]["gate_count"],
              len(snapshot.gates), selected["denominators"]["gate_count"],
              "gate denominator matches schema"),
        check("schema:required-surface-fields", ServiceReleasePlane.BOUNDARY,
              all(all(field in item.to_dict() for field in selected["resources"]["surfaces"]["required"]) for item in snapshot.surfaces),
              True, True, "surface rows contain required fields"),
        check("schema:required-artifact-fields", ServiceReleasePlane.BOUNDARY,
              all(all(field in item.to_dict() for field in selected["resources"]["artifacts"]["required"]) for item in snapshot.artifacts),
              True, True, "artifact rows contain required fields"),
        check("schema:required-gate-fields", ServiceReleasePlane.BOUNDARY,
              all(all(field in item.to_dict() for field in selected["resources"]["gates"]["required"]) for item in snapshot.gates),
              True, True, "gate rows contain required fields"),
        check("schema:public-keys", ServiceReleasePlane.BOUNDARY,
              not forbidden_keys(snapshot.to_dict()), forbidden_keys(snapshot.to_dict()), (),
              "schema projection contains no forbidden runtime metadata"),
    ]
    return tuple(checks)


def service_release_schema_address() -> str:
    """Return the content address of the current schema declaration."""

    return content_hash(service_release_schema(), prefix="service-release-schema")


__all__ = ["service_release_schema", "service_release_schema_address", "validate_service_release_schema"]
