"""Offline deployment bundle and federated assignment projections."""

from __future__ import annotations

from .coordination_architecture_contracts import (
    COORDINATION_CONTEXT,
    CoordinationAssignment,
    CoordinationDeploymentArtifact,
    CoordinationFixture,
    CoordinationState,
    addressed,
)


def build_coordination_deployment_artifacts(fixture: CoordinationFixture) -> tuple[CoordinationDeploymentArtifact, ...]:
    rows = (
        ("runtime-contract", "runtime manifest"),
        ("schema-contract", "projection schema"),
        ("source-index", "public source index"),
        ("test-vectors", "deterministic control vectors"),
        ("release-notes", "bounded release notes"),
    )
    artifacts = []
    for artifact_id, kind in rows:
        digest = addressed({"fixture_id": fixture.fixture_id, "artifact_id": artifact_id, "kind": kind}, "coordination-artifact-digest")
        body = {"artifact_id": artifact_id, "artifact_kind": kind, "digest": digest, "offline_capable": True}
        artifacts.append(CoordinationDeploymentArtifact(**body, content_address=addressed(body, "coordination-artifact")))
    return tuple(artifacts)


def build_coordination_assignments(fixture: CoordinationFixture) -> tuple[CoordinationAssignment, ...]:
    assignments = []
    for spec in fixture.operations:
        body = {
            "assignment_id": f"assignment:public-site:{spec.operation_id}",
            "site_id": "public-aggregate-site",
            "operation_id": spec.operation_id,
            "context_key": COORDINATION_CONTEXT,
            "eligible": True,
            "privacy_cost": 0,
            "state": CoordinationState.ACCEPTED,
        }
        assignments.append(CoordinationAssignment(**body, content_address=addressed(body, "coordination-assignment")))
    return tuple(assignments)


def audit_coordination_deployment(
    artifacts: tuple[CoordinationDeploymentArtifact, ...],
    assignments: tuple[CoordinationAssignment, ...],
) -> tuple[str, ...]:
    issues: list[str] = []
    if len(artifacts) != 5:
        issues.append("artifact_count_mismatch")
    if any(not item.offline_capable for item in artifacts):
        issues.append("offline_boundary_mismatch")
    if len(assignments) != 16:
        issues.append("assignment_count_mismatch")
    if any(not item.eligible or item.privacy_cost != 0 or item.context_key != COORDINATION_CONTEXT for item in assignments):
        issues.append("assignment_boundary_mismatch")
    return tuple(sorted(set(issues)))


__all__ = ["build_coordination_deployment_artifacts", "build_coordination_assignments", "audit_coordination_deployment"]
