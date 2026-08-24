"""Sanitized D11 artifact manifests."""

from __future__ import annotations

from .causal_architecture_contracts import (
    CausalArchitectureArtifact,
    CausalArchitectureDataAudit,
    CausalArchitectureEvaluation,
    CausalArchitectureFixture,
    CausalArchitectureLedger,
    CausalArchitectureReviewQueue,
    addressed,
)


def build_causal_architecture_artifacts(
    fixture: CausalArchitectureFixture,
    audit: CausalArchitectureDataAudit,
    evaluation: CausalArchitectureEvaluation,
    review_queue: CausalArchitectureReviewQueue,
    ledger: CausalArchitectureLedger,
) -> tuple[CausalArchitectureArtifact, ...]:
    definitions = (
        ("causal-source-registry", "source_registry", len(fixture.sources)),
        ("causal-operation-register", "operation_register", len(fixture.operations)),
        ("causal-receipt-export", "receipt_export", len(evaluation.receipts)),
        ("causal-review-queue", "review_queue", len(review_queue.items)),
        ("causal-ledger", "decision_ledger", len(ledger.events)),
        ("causal-release-summary", "release_summary", 1),
    )
    source_addresses = tuple(item.content_address for item in fixture.sources)
    return tuple(
        CausalArchitectureArtifact(
            artifact_id,
            artifact_type,
            "public_sanitized",
            addressed(
                {"artifact_id": artifact_id, "record_count": count, "audit": audit.content_address},
                "causal-artifact",
            ),
            source_addresses,
            count,
            True,
        )
        for artifact_id, artifact_type, count in definitions
    )


def causal_architecture_artifacts_are_safe(
    artifacts: tuple[CausalArchitectureArtifact, ...],
) -> bool:
    return len(artifacts) == 6 and all(
        item.review_safe
        and item.visibility == "public_sanitized"
        and item.content_address.startswith("sha256:")
        for item in artifacts
    )


__all__ = ["build_causal_architecture_artifacts", "causal_architecture_artifacts_are_safe"]
