"""Public access and retention policy for D04 release artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureArtifact,
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureAccessPolicy:
    audience: str
    allowed_media_types: tuple[str, ...]
    retention: str
    payload_boundary: str
    checks: tuple[ReferenceArchitectureCheck, ...]
    content_address: str


def reference_architecture_access_policy(
    artifacts: tuple[ReferenceArchitectureArtifact, ...],
) -> ReferenceArchitectureAccessPolicy:
    media_types = tuple(sorted({item.media_type for item in artifacts}))
    checks = (
        _check(
            "artifact-count", len(artifacts) == 6, len(artifacts), 6, "six artifacts are retained"
        ),
        _check(
            "media-types",
            all(item in {"application/json", "text/markdown"} for item in media_types),
            media_types,
            "JSON or Markdown",
            "formats are reviewable",
        ),
        _check(
            "retention",
            all(item.retention == "versioned-public-release" for item in artifacts),
            tuple(item.retention for item in artifacts),
            "versioned-public-release",
            "retention is explicit",
        ),
        _check(
            "address-joins",
            all(item.source_addresses for item in artifacts),
            len(artifacts),
            6,
            "artifacts retain upstream addresses",
        ),
    )
    body = {
        "audience": "public",
        "allowed_media_types": media_types,
        "retention": "versioned-public-release",
        "payload_boundary": "aggregate-only",
        "checks": checks,
    }
    return ReferenceArchitectureAccessPolicy(
        "public",
        media_types,
        "versioned-public-release",
        "aggregate-only",
        checks,
        addressed(body, "reference-access"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ReferenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        ReferenceArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-access-check"),
    )


__all__ = ["ReferenceArchitectureAccessPolicy", "reference_architecture_access_policy"]
