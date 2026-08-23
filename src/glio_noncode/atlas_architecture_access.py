"""Public access and retention policy for D05 atlas artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_architecture_contracts import (
    AtlasArchitectureArtifact,
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureAccessPolicy:
    audience: str
    allowed_media_types: tuple[str, ...]
    retention: str
    payload_boundary: str
    checks: tuple[AtlasArchitectureCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, object]:
        from .serialization import jsonable

        return jsonable(self)


def atlas_architecture_access_policy(
    artifacts: tuple[AtlasArchitectureArtifact, ...],
) -> AtlasArchitectureAccessPolicy:
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
    return AtlasArchitectureAccessPolicy(
        "public",
        media_types,
        "versioned-public-release",
        "aggregate-only",
        checks,
        addressed(body, "atlas-access"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.RELEASE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-access-check"),
    )


__all__ = ["AtlasArchitectureAccessPolicy", "atlas_architecture_access_policy"]
