"""Sanitized D10 artifact manifests."""

from __future__ import annotations

from .link_graph_architecture_contracts import (
    LinkGraphArchitectureArtifact,
    LinkGraphArchitectureDataAudit,
    LinkGraphArchitectureEvaluation,
    LinkGraphArchitectureFixture,
    LinkGraphArchitectureLedger,
    LinkGraphArchitectureReviewQueue,
    addressed,
)


def build_link_graph_architecture_artifacts(
    fixture: LinkGraphArchitectureFixture,
    audit: LinkGraphArchitectureDataAudit,
    evaluation: LinkGraphArchitectureEvaluation,
    review_queue: LinkGraphArchitectureReviewQueue,
    ledger: LinkGraphArchitectureLedger,
) -> tuple[LinkGraphArchitectureArtifact, ...]:
    definitions = (
        ("link-source-registry", "source_registry", len(fixture.sources)),
        ("link-operation-register", "operation_register", len(fixture.operations)),
        ("link-receipt-export", "receipt_export", len(evaluation.receipts)),
        ("link-review-queue", "review_queue", len(review_queue.items)),
        ("link-ledger", "decision_ledger", len(ledger.events)),
        ("link-release-summary", "release_summary", 1),
    )
    source_addresses = tuple(item.content_address for item in fixture.sources)
    return tuple(
        LinkGraphArchitectureArtifact(
            artifact_id,
            artifact_type,
            "public_sanitized",
            addressed(
                {"artifact_id": artifact_id, "record_count": count, "audit": audit.content_address},
                "link-artifact",
            ),
            source_addresses,
            count,
            True,
        )
        for artifact_id, artifact_type, count in definitions
    )


def link_graph_architecture_artifacts_are_safe(
    artifacts: tuple[LinkGraphArchitectureArtifact, ...],
) -> bool:
    return len(artifacts) == 6 and all(
        item.review_safe
        and item.visibility == "public_sanitized"
        and item.content_address.startswith("sha256:")
        for item in artifacts
    )


__all__ = ["build_link_graph_architecture_artifacts", "link_graph_architecture_artifacts_are_safe"]
