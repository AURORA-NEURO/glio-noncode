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
    kinds = (
        "manifest",
        "source_receipts",
        "operation_results",
        "evaluation_checks",
        "review_queue",
        "ledger",
        "schema_manifest",
        "release_receipt",
    )
    values = (
        fixture.to_dict(),
        tuple(item.to_dict() for item in fixture.sources),
        tuple(item.to_dict() for item in evaluation.results),
        tuple(item.to_dict() for item in evaluation.checks),
        {
            "held_controls": sum(
                item.observed_state.value != "accepted" for item in evaluation.results
            )
        },
        ledger.to_dict(),
        {"schema_id": "intake-architecture-d02", "privacy_scope": "public_aggregate"},
        {"rollback_pointer": "d02.2026.07.1", "offline_capable": True},
    )
    artifacts = []
    for kind, value in zip(kinds, values, strict=True):
        body = {
            "artifact_id": f"intake-artifact:{kind}",
            "artifact_kind": kind,
            "digest": addressed(value, "intake-artifact-digest"),
            "offline_capable": True,
        }
        artifacts.append(
            IntakeArchitectureBundleArtifact(
                **body, content_address=addressed(body, "intake-artifact")
            )
        )
    return tuple(artifacts)


def build_intake_architecture_release(
    artifacts: tuple[IntakeArchitectureBundleArtifact, ...],
) -> IntakeArchitectureRelease:
    blockers = tuple("offline_capability_missing" for item in artifacts if not item.offline_capable)
    body = {
        "release_id": "intake-release-d02",
        "version": "d02.2026.08.1",
        "state": IntakeArchitectureState.ACCEPTED
        if not blockers and len(artifacts) == 8
        else IntakeArchitectureState.REVIEW,
        "artifact_addresses": tuple(item.content_address for item in artifacts),
        "blockers": blockers,
        "rollback_version": "d02.2026.07.1",
    }
    return IntakeArchitectureRelease(**body, content_address=addressed(body, "intake-release"))


def verify_intake_architecture_release(release: IntakeArchitectureRelease) -> tuple[str, ...]:
    issues: list[str] = []
    if len(release.artifact_addresses) != 8:
        issues.append("artifact_denominator")
    if release.blockers:
        issues.extend(release.blockers)
    if not release.rollback_version:
        issues.append("rollback_version_missing")
    return tuple(sorted(set(issues)))


__all__ = [
    "build_intake_architecture_artifacts",
    "build_intake_architecture_release",
    "verify_intake_architecture_release",
]
