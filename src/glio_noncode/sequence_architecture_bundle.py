"""Release artifact and publication bundle construction for D06."""

from __future__ import annotations

from .sequence_architecture_contracts import (
    SequenceArchitectureArtifact,
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureRelease,
    SequenceArchitectureReviewQueue,
    SequenceArchitectureState,
    addressed,
)


def materialize_sequence_architecture_artifacts(
    fixture: SequenceArchitectureFixture,
    evaluation: SequenceArchitectureEvaluation,
    review_queue: SequenceArchitectureReviewQueue,
    validation_count: int,
    ledger_address: str,
) -> tuple[SequenceArchitectureArtifact, ...]:
    rows = (
        len(fixture.cases),
        len(evaluation.receipts),
        len(review_queue.items),
        64,
        len(evaluation.receipts),
        validation_count,
    )
    types = ("fixture", "evaluation", "review", "lineage", "metrics", "validation")
    return tuple(
        _artifact(
            f"D06-A{index:02d}", artifact_type, row_count, fixture.content_address, ledger_address
        )
        for index, (artifact_type, row_count) in enumerate(zip(types, rows, strict=True), 1)
    )


def release_sequence_architecture(
    fixture: SequenceArchitectureFixture,
    artifacts: tuple[SequenceArchitectureArtifact, ...],
    review_queue: SequenceArchitectureReviewQueue,
    quality_passed: bool,
) -> SequenceArchitectureRelease:
    state = (
        SequenceArchitectureState.PUBLISHED if quality_passed else SequenceArchitectureState.BLOCKED
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "artifact_addresses": tuple(item.content_address for item in artifacts),
        "review_count": len(review_queue.items),
    }
    return SequenceArchitectureRelease(
        fixture_id=fixture.fixture_id,
        state=state,
        artifact_ids=body["artifact_ids"],
        artifact_addresses=body["artifact_addresses"],
        review_count=len(review_queue.items),
        content_address=addressed(body, "sequence-release"),
    )


def _artifact(
    artifact_id: str, artifact_type: str, row_count: int, fixture_address: str, ledger_address: str
) -> SequenceArchitectureArtifact:
    body = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "media_type": "application/json",
        "row_count": row_count,
        "source_addresses": (fixture_address, ledger_address),
        "retention": "release",
    }
    return SequenceArchitectureArtifact(
        **body, content_address=addressed(body, "sequence-artifact")
    )


__all__ = ["materialize_sequence_architecture_artifacts", "release_sequence_architecture"]
