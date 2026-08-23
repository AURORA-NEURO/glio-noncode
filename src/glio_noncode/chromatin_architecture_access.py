"""Artifact visibility and access policy for D07 release surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import ChromatinArchitectureArtifact, addressed
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureAccessDecision:
    artifact_id: str
    visibility: str
    roles: tuple[str, ...]
    permitted: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureAccessReport:
    decisions: tuple[ChromatinArchitectureAccessDecision, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def chromatin_architecture_access_policy(
    artifacts: tuple[ChromatinArchitectureArtifact, ...],
) -> ChromatinArchitectureAccessReport:
    decisions = tuple(
        ChromatinArchitectureAccessDecision(
            artifact_id=artifact.artifact_id,
            visibility=artifact.visibility,
            roles=("reader", "reviewer", "release_manager")
            if artifact.review_safe
            else ("reviewer", "release_manager"),
            permitted=artifact.review_safe and artifact.visibility in {"public", "review"},
            reason="sanitized aggregate artifact is available to its declared roles"
            if artifact.review_safe
            else "artifact remains restricted until review closes",
            content_address=addressed(
                {
                    "artifact_id": artifact.artifact_id,
                    "visibility": artifact.visibility,
                    "review_safe": artifact.review_safe,
                },
                "chromatin-access-decision",
            ),
        )
        for artifact in artifacts
    )
    body = {"decisions": decisions}
    return ChromatinArchitectureAccessReport(
        decisions,
        bool(decisions) and all(item.permitted for item in decisions),
        addressed(body, "chromatin-access"),
    )


__all__ = [
    "ChromatinArchitectureAccessDecision",
    "ChromatinArchitectureAccessReport",
    "chromatin_architecture_access_policy",
]
