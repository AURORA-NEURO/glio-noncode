"""Access and retention policy for public specimen architecture artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureArtifact,
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureAccessPolicy:
    audience: str
    allowed_media_types: tuple[str, ...]
    retention: str
    payload_boundary: str
    checks: tuple[SpecimenArchitectureCheck, ...]
    content_address: str


def specimen_architecture_access_policy(
    artifacts: tuple[SpecimenArchitectureArtifact, ...],
) -> SpecimenArchitectureAccessPolicy:
    """Close access on aggregate artifacts and reject unbounded media types."""

    media_types = tuple(sorted({artifact.media_type for artifact in artifacts}))
    checks = (
        _check("artifact-count", len(artifacts) == 6, len(artifacts), 6, "six release artifacts"),
        _check(
            "media-types",
            all(media in {"application/json", "text/markdown"} for media in media_types),
            media_types,
            "JSON or Markdown",
            "reviewable export formats",
        ),
        _check(
            "retention",
            all(artifact.retention == "versioned-public-release" for artifact in artifacts),
            tuple(artifact.retention for artifact in artifacts),
            "versioned-public-release",
            "retention is explicit",
        ),
        _check(
            "source-joins",
            all(artifact.source_addresses for artifact in artifacts),
            len(artifacts),
            6,
            "artifacts retain upstream addresses",
        ),
    )
    body = {
        "audience": "public",
        "media_types": media_types,
        "retention": "versioned-public-release",
        "payload_boundary": "aggregate-only",
        "checks": checks,
    }
    return SpecimenArchitectureAccessPolicy(
        "public",
        media_types,
        "versioned-public-release",
        "aggregate-only",
        checks,
        addressed(body, "specimen-access"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-access-check"),
    )


__all__ = ["SpecimenArchitectureAccessPolicy", "specimen_architecture_access_policy"]
