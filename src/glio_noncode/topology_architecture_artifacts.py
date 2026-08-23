"""Six review-safe D09 artifact descriptors."""

from __future__ import annotations

from .topology_architecture_contracts import (
    TopologyArchitectureArtifact,
    TopologyArchitectureDataAudit,
    TopologyArchitectureEvaluation,
    TopologyArchitectureFixture,
    TopologyArchitectureLedger,
    TopologyArchitectureReviewQueue,
    addressed,
)


def build_topology_architecture_artifacts(
    fixture: TopologyArchitectureFixture,
    audit: TopologyArchitectureDataAudit,
    evaluation: TopologyArchitectureEvaluation,
    review_queue: TopologyArchitectureReviewQueue,
    ledger: TopologyArchitectureLedger,
) -> tuple[TopologyArchitectureArtifact, ...]:
    rows = (
        ("fixture", fixture.content_address, len(fixture.cases)),
        ("audit", audit.content_address, len(audit.checks)),
        ("evaluation", evaluation.content_address, len(evaluation.receipts)),
        ("review_queue", review_queue.content_address, len(review_queue.items)),
        ("ledger", ledger.content_address, len(ledger.events)),
        (
            "source_registry",
            addressed([item.to_dict() for item in fixture.sources], "topology-sources"),
            len(fixture.sources),
        ),
    )
    source_addresses = tuple(item.content_address for item in fixture.sources)
    artifacts: list[TopologyArchitectureArtifact] = []
    for index, (artifact_type, source_address, record_count) in enumerate(rows, start=1):
        body = {
            "artifact_id": f"D09-A{index:02d}",
            "artifact_type": artifact_type,
            "visibility": "public_aggregate",
            "source_address": source_address,
            "source_addresses": source_addresses,
            "record_count": record_count,
            "review_safe": True,
        }
        artifacts.append(
            TopologyArchitectureArtifact(
                artifact_id=body["artifact_id"],
                artifact_type=artifact_type,
                visibility="public_aggregate",
                content_address=addressed(body, "topology-artifact"),
                source_addresses=source_addresses,
                record_count=record_count,
                review_safe=True,
            )
        )
    return tuple(artifacts)


def topology_architecture_artifacts_are_safe(
    artifacts: tuple[TopologyArchitectureArtifact, ...],
) -> bool:
    return len(artifacts) == 6 and all(
        item.visibility == "public_aggregate" and item.review_safe for item in artifacts
    )


__all__ = ["build_topology_architecture_artifacts", "topology_architecture_artifacts_are_safe"]
