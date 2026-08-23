"""Offline bundle, release, and deterministic export receipts."""

from __future__ import annotations

from .intake_architecture_contracts import (
    IntakeArchitectureBundleArtifact,
    IntakeArchitectureEvaluation,
    IntakeArchitectureFixture,
    IntakeArchitectureLedger,
    IntakeArchitectureRelease,
    IntakeArchitectureState,
    addressed,
)


def build_intake_architecture_artifacts(
    fixture: IntakeArchitectureFixture,
    evaluation: IntakeArchitectureEvaluation,
    ledger: IntakeArchitectureLedger,
) -> tuple[IntakeArchitectureBundleArtifact, ...]:
    kinds = ("manifest", "source_receipts", "operation_results", "review_queue", "ledger")
    values = (fixture.to_dict(), evaluation.to_dict(), ledger.to_dict(), {"fixture": fixture.fixture_id}, {"events": len(ledger.events)})
    artifacts = []
    for kind, value in zip(kinds, values, strict=True):
        body = {"artifact_id": f"intake-artifact:{kind}", "artifact_kind": kind, "digest": addressed(value, "intake-artifact-digest"), "offline_capable": True}
        artifacts.append(IntakeArchitectureBundleArtifact(**body, content_address=addressed(body, "intake-artifact")))
    return tuple(artifacts)


def build_intake_architecture_release(artifacts: tuple[IntakeArchitectureBundleArtifact, ...]) -> IntakeArchitectureRelease:
    blockers = tuple("offline_capability_missing" for item in artifacts if not item.offline_capable)
    body = {
        "release_id": "intake-release-d01",
        "version": "d01.2026.08.1",
        "state": IntakeArchitectureState.ACCEPTED if not blockers and len(artifacts) == 5 else IntakeArchitectureState.REVIEW,
        "artifact_addresses": tuple(item.content_address for item in artifacts),
        "blockers": blockers,
        "rollback_version": "d01.2026.07.1",
    }
    return IntakeArchitectureRelease(**body, content_address=addressed(body, "intake-release"))


def verify_intake_architecture_release(release: IntakeArchitectureRelease) -> tuple[str, ...]:
    issues: list[str] = []
    if len(release.artifact_addresses) != 5:
        issues.append("artifact_denominator")
    if release.blockers:
        issues.extend(release.blockers)
    if not release.rollback_version:
        issues.append("rollback_version_missing")
    return tuple(sorted(set(issues)))


__all__ = ["build_intake_architecture_artifacts", "build_intake_architecture_release", "verify_intake_architecture_release"]
