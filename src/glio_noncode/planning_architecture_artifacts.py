"""Review-safe D13 artifact inventory."""

from __future__ import annotations

from .planning_architecture_contracts import (
    PlanningArchitectureArtifact,
    PlanningArchitectureDataAudit,
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    PlanningArchitectureLedger,
    PlanningArchitectureReviewQueue,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture


def build_planning_architecture_artifacts(
    fixture: PlanningArchitectureFixture | None = None,
    audit: PlanningArchitectureDataAudit | None = None,
    evaluation: PlanningArchitectureEvaluation | None = None,
    review: PlanningArchitectureReviewQueue | None = None,
    ledger: PlanningArchitectureLedger | None = None,
) -> tuple[PlanningArchitectureArtifact, ...]:
    selected = fixture or default_planning_architecture_fixture()
    source_addresses = tuple(item.content_address for item in selected.sources)
    resolved_audit = audit or __import__(
        "glio_noncode.planning_architecture_public_data",
        fromlist=["audit_planning_architecture_data"],
    ).audit_planning_architecture_data(selected)
    resolved_evaluation = evaluation
    resolved_review = review
    resolved_ledger = ledger
    if resolved_evaluation is None:
        resolved_evaluation = __import__(
            "glio_noncode.planning_architecture_operations",
            fromlist=["evaluate_planning_architecture_fixture"],
        ).evaluate_planning_architecture_fixture(selected)
    if resolved_review is None:
        resolved_review = __import__(
            "glio_noncode.planning_architecture_review",
            fromlist=["build_planning_architecture_review_queue"],
        ).build_planning_architecture_review_queue(resolved_evaluation)
    if resolved_ledger is None:
        resolved_ledger = __import__(
            "glio_noncode.planning_architecture_ledger",
            fromlist=["build_planning_architecture_ledger"],
        ).build_planning_architecture_ledger(selected, resolved_evaluation)
    specs = (
        ("fixture", "public_aggregate", selected.content_address, len(selected.cases)),
        (
            "source-registry",
            "public_aggregate",
            addressed(selected.sources, "planning-sources"),
            len(selected.sources),
        ),
        (
            "operation-catalog",
            "public_aggregate",
            addressed(selected.operations, "planning-operations"),
            len(selected.operations),
        ),
        (
            "evaluation",
            "public_aggregate",
            resolved_evaluation.content_address,
            len(resolved_evaluation.executions),
        ),
        (
            "review-queue",
            "review_projection",
            resolved_review.content_address,
            len(resolved_review.items),
        ),
        (
            "event-ledger",
            "audit_projection",
            resolved_ledger.content_address,
            len(resolved_ledger.events),
        ),
    )
    artifacts: list[PlanningArchitectureArtifact] = []
    for ordinal, (artifact_type, visibility, content_address, count) in enumerate(specs, start=1):
        body = {
            "artifact_id": f"D13-A{ordinal:02d}",
            "artifact_type": artifact_type,
            "visibility": visibility,
            "content_address": content_address,
            "source_addresses": source_addresses,
            "record_count": count,
            "review_safe": resolved_audit.accepted,
        }
        artifacts.append(PlanningArchitectureArtifact(**body))
    return tuple(artifacts)


def planning_architecture_artifacts_are_safe(
    artifacts: tuple[PlanningArchitectureArtifact, ...],
) -> bool:
    return (
        len(artifacts) == 6
        and all(item.review_safe for item in artifacts)
        and all(item.content_address and item.source_addresses for item in artifacts)
        and len({item.artifact_id for item in artifacts}) == len(artifacts)
    )


def planning_architecture_artifact_summary(
    artifacts: tuple[PlanningArchitectureArtifact, ...],
) -> dict[str, object]:
    return {
        "artifact_count": len(artifacts),
        "safe": planning_architecture_artifacts_are_safe(artifacts),
        "artifact_ids": [item.artifact_id for item in artifacts],
        "visibility_counts": {
            value: sum(item.visibility == value for item in artifacts)
            for value in sorted({item.visibility for item in artifacts})
        },
    }


__all__ = [
    "build_planning_architecture_artifacts",
    "planning_architecture_artifact_summary",
    "planning_architecture_artifacts_are_safe",
]
