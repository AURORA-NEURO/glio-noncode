"""Sanitized artifact materialization for the D07 release bundle."""

from __future__ import annotations

from .chromatin_architecture_contracts import (
    ChromatinArchitectureArtifact,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    ChromatinArchitectureLedger,
    ChromatinArchitectureReviewQueue,
    addressed,
)
from .chromatin_architecture_lineage import ChromatinArchitectureLineage
from .chromatin_architecture_metrics import ChromatinArchitectureMetrics
from .chromatin_architecture_policy import ChromatinArchitecturePolicyReport


def materialize_chromatin_architecture_artifacts(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
    policy: ChromatinArchitecturePolicyReport,
    review: ChromatinArchitectureReviewQueue,
    lineage: ChromatinArchitectureLineage,
    ledger: ChromatinArchitectureLedger,
    metrics: ChromatinArchitectureMetrics,
) -> tuple[ChromatinArchitectureArtifact, ...]:
    rows = (
        ("fixture", "public", fixture.content_address, len(fixture.cases)),
        ("evaluation", "public", evaluation.content_address, len(evaluation.receipts)),
        ("policy", "review", policy.content_address, len(policy.decisions)),
        ("review", "review", review.content_address, len(review.items)),
        ("lineage", "public", lineage.content_address, len(lineage.links)),
        ("metrics", "public", metrics.content_address, len(evaluation.receipts)),
    )
    return tuple(
        ChromatinArchitectureArtifact(
            artifact_id=f"d07-{artifact_type}",
            artifact_type=artifact_type,
            visibility=visibility,
            content_address=addressed(
                {
                    "artifact_type": artifact_type,
                    "address": source_address,
                    "record_count": record_count,
                },
                "chromatin-artifact",
            ),
            source_addresses=(source_address, ledger.content_address),
            record_count=record_count,
            review_safe=artifact_type not in {"policy", "review"} or bool(review.items),
        )
        for artifact_type, visibility, source_address, record_count in rows
    )


__all__ = ["materialize_chromatin_architecture_artifacts"]
