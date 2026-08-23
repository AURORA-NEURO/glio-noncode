"""Review-safe artifact descriptors for the D08 release bundle."""

from __future__ import annotations

from .cell_state_architecture_contracts import (
    CellStateArchitectureArtifact,
    CellStateArchitectureDataAudit,
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    CellStateArchitectureLedger,
    CellStateArchitectureReviewQueue,
    addressed,
)


def build_cell_state_architecture_artifacts(
    fixture: CellStateArchitectureFixture,
    audit: CellStateArchitectureDataAudit,
    evaluation: CellStateArchitectureEvaluation,
    review_queue: CellStateArchitectureReviewQueue,
    ledger: CellStateArchitectureLedger,
) -> tuple[CellStateArchitectureArtifact, ...]:
    rows = (
        ("fixture", fixture.content_address, len(fixture.cases), True),
        ("audit", audit.content_address, len(audit.checks), True),
        ("evaluation", evaluation.content_address, len(evaluation.receipts), True),
        ("review_queue", review_queue.content_address, len(review_queue.items), True),
        ("ledger", ledger.content_address, len(ledger.events), True),
        (
            "source_registry",
            addressed([item.to_dict() for item in fixture.sources], "cell-state-sources"),
            len(fixture.sources),
            True,
        ),
    )
    artifacts: list[CellStateArchitectureArtifact] = []
    source_addresses = tuple(item.content_address for item in fixture.sources)
    for index, (artifact_type, content_address, record_count, review_safe) in enumerate(
        rows, start=1
    ):
        body = {
            "artifact_id": f"D08-A{index:02d}",
            "artifact_type": artifact_type,
            "visibility": "public_aggregate",
            "source_address": content_address,
            "source_addresses": source_addresses,
            "record_count": record_count,
            "review_safe": review_safe,
        }
        artifacts.append(
            CellStateArchitectureArtifact(
                artifact_id=body["artifact_id"],
                artifact_type=body["artifact_type"],
                visibility=body["visibility"],
                content_address=addressed(body, "cell-state-artifact"),
                source_addresses=body["source_addresses"],
                record_count=body["record_count"],
                review_safe=body["review_safe"],
            )
        )
    return tuple(artifacts)


def artifacts_are_review_safe(artifacts: tuple[CellStateArchitectureArtifact, ...]) -> bool:
    return len(artifacts) == 6 and all(
        item.visibility == "public_aggregate" and item.review_safe for item in artifacts
    )


__all__ = ["artifacts_are_review_safe", "build_cell_state_architecture_artifacts"]
