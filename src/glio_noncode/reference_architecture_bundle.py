"""Six-artifact release bundle construction for D04."""

from __future__ import annotations

from .reference_architecture_contracts import (
    REFERENCE_ARCHITECTURE_ARTIFACT_COUNT,
    ReferenceArchitectureArtifact,
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureFixture,
    ReferenceArchitectureLedger,
    ReferenceArchitectureRelease,
    ReferenceArchitectureReviewQueue,
    ReferenceArchitectureState,
    addressed,
)
from .reference_architecture_metrics import ReferenceArchitectureMetrics
from .serialization import content_hash


def materialize_reference_architecture_artifacts(
    fixture: ReferenceArchitectureFixture,
    evaluation: ReferenceArchitectureEvaluation,
    review_queue: ReferenceArchitectureReviewQueue,
    ledger: ReferenceArchitectureLedger,
    metrics: ReferenceArchitectureMetrics,
) -> tuple[ReferenceArchitectureArtifact, ...]:
    addresses = (
        fixture.content_address,
        evaluation.content_address,
        review_queue.content_address,
        ledger.content_address,
        metrics.content_address,
    )
    specs = (
        ("fixture", "fixture_json", "application/json", len(fixture.cases)),
        ("evaluation", "evaluation_json", "application/json", len(evaluation.receipts)),
        ("review", "review_json", "application/json", len(review_queue.items)),
        ("lineage", "lineage_json", "application/json", len(ledger.events)),
        ("metrics", "metrics_json", "application/json", metrics.operation_count),
        ("release_notes", "release_notes", "text/markdown", 16),
    )
    artifacts: list[ReferenceArchitectureArtifact] = []
    for artifact_id, artifact_type, media_type, row_count in specs:
        body = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "media_type": media_type,
            "row_count": row_count,
            "source_addresses": addresses,
            "retention": "versioned-public-release",
        }
        artifacts.append(
            ReferenceArchitectureArtifact(
                artifact_id,
                artifact_type,
                media_type,
                row_count,
                addresses,
                content_hash(body),
                "versioned-public-release",
            )
        )
    return tuple(artifacts)


def release_reference_architecture(
    fixture: ReferenceArchitectureFixture,
    evaluation: ReferenceArchitectureEvaluation,
    review_queue: ReferenceArchitectureReviewQueue,
    ledger: ReferenceArchitectureLedger,
    artifacts: tuple[ReferenceArchitectureArtifact, ...],
    checks: tuple[object, ...],
) -> ReferenceArchitectureRelease:
    passed_checks = all(getattr(item, "passed", False) for item in checks)
    published = (
        evaluation.accepted
        and review_queue.accepted
        and ledger.accepted
        and len(artifacts) == REFERENCE_ARCHITECTURE_ARTIFACT_COUNT
        and passed_checks
    )
    state = (
        ReferenceArchitectureState.PUBLISHED if published else ReferenceArchitectureState.BLOCKED
    )
    rollback_key = f"rollback:{fixture.content_address}"
    body = {
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifacts": artifacts,
        "checks": checks,
        "rollback_key": rollback_key,
    }
    return ReferenceArchitectureRelease(
        fixture.fixture_id,
        state,
        artifacts,
        rollback_key,
        tuple(checks),
        addressed(body, "reference-release"),
    )


__all__ = ["materialize_reference_architecture_artifacts", "release_reference_architecture"]
