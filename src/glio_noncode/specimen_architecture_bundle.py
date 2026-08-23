"""Materialize the six bounded artifacts that make a run releasable."""

from __future__ import annotations

from .serialization import content_hash
from .specimen_architecture_contracts import (
    SpecimenArchitectureArtifact,
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureFixture,
    SpecimenArchitectureLedger,
    SpecimenArchitectureRelease,
    SpecimenArchitectureReviewQueue,
    SpecimenArchitectureState,
    addressed,
)
from .specimen_architecture_metrics import SpecimenArchitectureMetrics


def materialize_specimen_architecture_artifacts(
    fixture: SpecimenArchitectureFixture,
    evaluation: SpecimenArchitectureEvaluation,
    review_queue: SpecimenArchitectureReviewQueue,
    ledger: SpecimenArchitectureLedger,
    metrics: SpecimenArchitectureMetrics,
) -> tuple[SpecimenArchitectureArtifact, ...]:
    """Create six deterministic release artifacts with source address joins."""

    artifact_specs = (
        ("fixture", "fixture_json", "application/json", len(fixture.cases)),
        ("evaluation", "evaluation_json", "application/json", len(evaluation.receipts)),
        ("review", "review_json", "application/json", len(review_queue.items)),
        ("lineage", "lineage_json", "application/json", len(ledger.events)),
        ("metrics", "metrics_json", "application/json", metrics.operation_count),
        ("release_notes", "release_notes", "text/markdown", 16),
    )
    addresses = (
        fixture.content_address,
        evaluation.content_address,
        review_queue.content_address,
        ledger.content_address,
        metrics.content_address,
    )
    artifacts: list[SpecimenArchitectureArtifact] = []
    for artifact_id, artifact_type, media_type, row_count in artifact_specs:
        body = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "media_type": media_type,
            "row_count": row_count,
            "source_addresses": addresses,
            "retention": "versioned-public-release",
        }
        artifacts.append(
            SpecimenArchitectureArtifact(
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


def release_specimen_architecture(
    fixture: SpecimenArchitectureFixture,
    evaluation: SpecimenArchitectureEvaluation,
    review_queue: SpecimenArchitectureReviewQueue,
    ledger: SpecimenArchitectureLedger,
    artifacts: tuple[SpecimenArchitectureArtifact, ...],
    checks: tuple[object, ...],
) -> SpecimenArchitectureRelease:
    """Gate publication on evaluation, review, lineage, artifacts, and checks."""

    passed_checks = all(getattr(check, "passed", False) for check in checks)
    published = (
        evaluation.accepted
        and review_queue.accepted
        and ledger.accepted
        and len(artifacts) == 6
        and passed_checks
    )
    state = SpecimenArchitectureState.PUBLISHED if published else SpecimenArchitectureState.BLOCKED
    body = {
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifacts": artifacts,
        "checks": checks,
        "rollback_key": f"rollback:{fixture.content_address}",
    }
    return SpecimenArchitectureRelease(
        fixture.fixture_id,
        state,
        artifacts,
        body["rollback_key"],
        tuple(checks),
        addressed(body, "specimen-release"),
    )


__all__ = ["materialize_specimen_architecture_artifacts", "release_specimen_architecture"]
