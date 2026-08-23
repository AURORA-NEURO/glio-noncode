"""Artifact access policy for the public D06 release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureArtifact,
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureAccessPolicy:
    artifact_ids: tuple[str, ...]
    public_artifact_count: int
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def sequence_architecture_access_policy(
    artifacts: tuple[SequenceArchitectureArtifact, ...],
) -> SequenceArchitectureAccessPolicy:
    checks = (
        _check(
            "access-count",
            len(artifacts) == 6,
            len(artifacts),
            6,
            "six release artifacts are available",
        ),
        _check(
            "access-addresses",
            all(item.content_address.startswith("sha256:") for item in artifacts),
            sum(item.content_address.startswith("sha256:") for item in artifacts),
            len(artifacts),
            "artifacts are addressed",
        ),
        _check(
            "access-retention",
            all(item.retention == "release" for item in artifacts),
            sum(item.retention == "release" for item in artifacts),
            len(artifacts),
            "release artifacts retain release policy",
        ),
        _check(
            "access-media",
            all(item.media_type == "application/json" for item in artifacts),
            sum(item.media_type == "application/json" for item in artifacts),
            len(artifacts),
            "aggregate artifacts use JSON interchange",
        ),
    )
    body = {"artifact_ids": tuple(item.artifact_id for item in artifacts), "checks": checks}
    return SequenceArchitectureAccessPolicy(
        artifact_ids=body["artifact_ids"],
        public_artifact_count=len(artifacts),
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-access"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.RELEASE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-access-check"),
    )


__all__ = ["SequenceArchitectureAccessPolicy", "sequence_architecture_access_policy"]
