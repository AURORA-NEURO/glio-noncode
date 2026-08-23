"""Release and rollback gate for the coordination architecture."""

from __future__ import annotations

from .coordination_architecture_contracts import CoordinationDeploymentArtifact, CoordinationRelease, CoordinationState, addressed


def build_coordination_release(
    artifacts: tuple[CoordinationDeploymentArtifact, ...],
    *,
    version: str = "coordination-2026.08.23",
    blockers: tuple[str, ...] = (),
) -> CoordinationRelease:
    addresses = tuple(item.content_address for item in artifacts)
    state = CoordinationState.ACCEPTED if artifacts and not blockers and all(item.offline_capable for item in artifacts) else CoordinationState.REVIEW
    body = {
        "release_id": f"release:{version}",
        "version": version,
        "state": state,
        "artifact_addresses": addresses,
        "blockers": blockers,
        "rollback_version": "coordination-previous",
    }
    return CoordinationRelease(**body, content_address=addressed(body, "coordination-release"))


def verify_coordination_release(release: CoordinationRelease) -> tuple[str, ...]:
    issues: list[str] = []
    if release.state is CoordinationState.ACCEPTED and release.blockers:
        issues.append("accepted_release_has_blockers")
    if not release.rollback_version:
        issues.append("rollback_version_missing")
    if len(set(release.artifact_addresses)) != len(release.artifact_addresses):
        issues.append("duplicate_artifact_address")
    return tuple(sorted(set(issues)))


__all__ = ["build_coordination_release", "verify_coordination_release"]
