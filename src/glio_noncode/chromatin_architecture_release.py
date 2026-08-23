"""Release-boundary construction for D07."""

from __future__ import annotations

from .chromatin_architecture_contracts import (
    ChromatinArchitectureArtifact,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    ChromatinArchitectureRelease,
    ChromatinArchitectureState,
    addressed,
)


def release_chromatin_architecture(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
    artifacts: tuple[ChromatinArchitectureArtifact, ...],
    *,
    quality_accepted: bool = True,
) -> ChromatinArchitectureRelease:
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    accepted = quality_accepted and evaluation.accepted and len(artifacts) == 6
    state = ChromatinArchitectureState.PUBLISHED if accepted else ChromatinArchitectureState.BLOCKED
    limitations = (
        "public aggregate receipts do not identify individuals or patients",
        "signal, methylation, concordance, and imputation outputs remain descriptive",
        "family adapters do not establish clinical, causal, or treatment conclusions",
        "foreign, malformed, and identity-conflict controls remain review-held",
    )
    body = {
        "release_id": "d07-chromatin-architecture-release-v1",
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifact_ids": artifact_ids,
        "quality_accepted": quality_accepted,
        "evaluation_address": evaluation.content_address,
        "limitations": limitations,
    }
    return ChromatinArchitectureRelease(
        release_id="d07-chromatin-architecture-release-v1",
        fixture_id=fixture.fixture_id,
        state=state,
        artifact_ids=artifact_ids,
        provenance_address=addressed(
            {"evaluation": evaluation.content_address, "artifacts": artifact_ids},
            "chromatin-release-provenance",
        ),
        limitations=limitations,
        content_address=addressed(body, "chromatin-release"),
    )


__all__ = ["release_chromatin_architecture"]
