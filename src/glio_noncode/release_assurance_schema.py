"""Machine-readable schema and validation for release assurance."""

from __future__ import annotations

from typing import Any

from .release_assurance_contracts import (
    RELEASE_ASSURANCE_CHECK_COUNT,
    RELEASE_ASSURANCE_DOMAIN_COUNT,
    RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
    RELEASE_ASSURANCE_SCHEMA_VERSION,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .release_assurance_support import forbidden_keys
from .serialization import content_hash


def release_assurance_schema() -> dict[str, Any]:
    """Return the public contract for the whole-product assurance object."""

    return {
        "version": RELEASE_ASSURANCE_SCHEMA_VERSION,
        "boundary": "public aggregate release readiness only",
        "resources": {
            "domains": {"key": "domain_id", "required": ["domain_id", "source_address", "accepted"]},
            "evidence": {"key": "link_id", "required": ["link_id", "domain_id", "source_address"]},
            "checks": {"key": "check_id", "required": ["check_id", "domain_id", "plane", "passed"]},
        },
        "denominators": {
            "domain_count": RELEASE_ASSURANCE_DOMAIN_COUNT,
            "evidence_count": RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
            "check_count": RELEASE_ASSURANCE_CHECK_COUNT,
        },
        "public_boundary": {
            "forbidden_key_policy": "recursive-key-and-token-filter",
            "source_records": "aggregate-only",
            "exact_byte_exports": True,
        },
    }


def validate_release_assurance_schema(
    snapshot: ReleaseAssuranceSnapshot,
    schema: dict[str, Any] | None = None,
) -> tuple:
    """Validate required fields, denominators, and public boundary."""

    selected = schema or release_assurance_schema()
    checks = [
        check("schema:version", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              selected.get("version") == RELEASE_ASSURANCE_SCHEMA_VERSION,
              selected.get("version"), RELEASE_ASSURANCE_SCHEMA_VERSION,
              "schema version is current"),
        check("schema:domain-count", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              len(snapshot.domains) == selected["denominators"]["domain_count"],
              len(snapshot.domains), selected["denominators"]["domain_count"],
              "domain denominator matches schema"),
        check("schema:evidence-count", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              len(snapshot.evidence) == selected["denominators"]["evidence_count"],
              len(snapshot.evidence), selected["denominators"]["evidence_count"],
              "evidence denominator matches schema"),
        check("schema:check-count", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              len(snapshot.checks) == selected["denominators"]["check_count"],
              len(snapshot.checks), selected["denominators"]["check_count"],
              "check denominator matches schema"),
        check("schema:domain-fields", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(all(field in item.to_dict() for field in selected["resources"]["domains"]["required"]) for item in snapshot.domains),
              True, True, "domain rows contain required fields"),
        check("schema:evidence-fields", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(all(field in item.to_dict() for field in selected["resources"]["evidence"]["required"]) for item in snapshot.evidence),
              True, True, "evidence rows contain required fields"),
        check("schema:check-fields", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(all(field in item.to_dict() for field in selected["resources"]["checks"]["required"]) for item in snapshot.checks),
              True, True, "check rows contain required fields"),
        check("schema:public-keys", "schema", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              not forbidden_keys(snapshot.to_dict()), forbidden_keys(snapshot.to_dict()), (),
              "assurance snapshot contains no forbidden runtime metadata"),
    ]
    return tuple(checks)


def release_assurance_schema_address() -> str:
    """Return the current schema declaration address."""

    return content_hash(release_assurance_schema(), prefix="release-assurance-schema")


__all__ = [
    "release_assurance_schema",
    "release_assurance_schema_address",
    "validate_release_assurance_schema",
]
