"""D12 review-safe artifact inventory."""

from __future__ import annotations

from .cohort_architecture_contracts import (
    CohortArchitectureArtifact,
    CohortArchitectureDataAudit,
    CohortArchitectureEvaluation,
    CohortArchitectureFixture,
    CohortArchitectureLedger,
    CohortArchitectureReviewQueue,
    addressed,
)


def build_cohort_architecture_artifacts(
    fixture: CohortArchitectureFixture,
    audit: CohortArchitectureDataAudit,
    evaluation: CohortArchitectureEvaluation,
    review: CohortArchitectureReviewQueue,
    ledger: CohortArchitectureLedger,
) -> tuple[CohortArchitectureArtifact, ...]:
    source_addresses = tuple(item.content_address for item in fixture.sources)
    definitions = (
        ("fixture", "public_fixture", len(fixture.cases)),
        ("audit", "data_audit", len(audit.checks)),
        ("evaluation", "evaluation_receipts", len(evaluation.receipts)),
        ("review", "review_queue", len(review.items)),
        ("ledger", "event_ledger", len(ledger.events)),
        ("release_projection", "release_projection", len(fixture.operations)),
    )
    artifacts = []
    for artifact_id, artifact_type, count in definitions:
        body = {
            "artifact_id": f"cohort-{artifact_id}",
            "artifact_type": artifact_type,
            "visibility": "public_aggregate_review_safe",
            "source_addresses": source_addresses,
            "record_count": count,
            "review_safe": True,
        }
        artifacts.append(
            CohortArchitectureArtifact(
                **body,
                content_address=addressed(body, "cohort-artifact"),
            )
        )
    return tuple(artifacts)


def cohort_architecture_artifacts_are_safe(
    artifacts: tuple[CohortArchitectureArtifact, ...],
) -> bool:
    return (
        len(artifacts) == 6
        and all(item.review_safe for item in artifacts)
        and all(item.visibility == "public_aggregate_review_safe" for item in artifacts)
        and all(item.content_address.startswith("sha256:") for item in artifacts)
    )


__all__ = ["build_cohort_architecture_artifacts", "cohort_architecture_artifacts_are_safe"]
