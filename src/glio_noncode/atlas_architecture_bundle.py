"""Six-artifact D05 atlas release bundle construction."""

from __future__ import annotations

from .atlas_architecture_contracts import (
    ATLAS_ARCHITECTURE_ARTIFACT_COUNT,
    AtlasArchitectureArtifact,
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitectureLedger,
    AtlasArchitectureRelease,
    AtlasArchitectureReviewQueue,
    AtlasArchitectureState,
    addressed,
)
from .atlas_architecture_metrics import AtlasArchitectureMetrics


def materialize_atlas_architecture_artifacts(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
    review_queue: AtlasArchitectureReviewQueue,
    ledger: AtlasArchitectureLedger,
    metrics: AtlasArchitectureMetrics,
) -> tuple[AtlasArchitectureArtifact, ...]:
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
    artifacts: list[AtlasArchitectureArtifact] = []
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
            AtlasArchitectureArtifact(
                artifact_id,
                artifact_type,
                media_type,
                row_count,
                addresses,
                addressed(body, "atlas-artifact"),
                "versioned-public-release",
            )
        )
    return tuple(artifacts)


def release_atlas_architecture(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
    review_queue: AtlasArchitectureReviewQueue,
    ledger: AtlasArchitectureLedger,
    artifacts: tuple[AtlasArchitectureArtifact, ...],
    checks: tuple[object, ...],
) -> AtlasArchitectureRelease:
    passed_checks = all(getattr(item, "passed", False) for item in checks)
    published = (
        evaluation.accepted
        and review_queue.accepted
        and ledger.accepted
        and len(artifacts) == ATLAS_ARCHITECTURE_ARTIFACT_COUNT
        and passed_checks
    )
    state = AtlasArchitectureState.PUBLISHED if published else AtlasArchitectureState.BLOCKED
    rollback_key = f"rollback:{fixture.content_address}"
    body = {
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifacts": artifacts,
        "checks": checks,
        "rollback_key": rollback_key,
    }
    return AtlasArchitectureRelease(
        fixture.fixture_id,
        state,
        artifacts,
        rollback_key,
        tuple(checks),
        addressed(body, "atlas-release"),
    )


__all__ = ["materialize_atlas_architecture_artifacts", "release_atlas_architecture"]
