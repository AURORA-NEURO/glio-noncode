"""Manifest assembly for the six D08 artifacts."""

from __future__ import annotations

from .cell_state_architecture_contracts import (
    CellStateArchitectureArtifact,
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    addressed,
)


def build_cell_state_architecture_bundle(
    fixture: CellStateArchitectureFixture,
    evaluation: CellStateArchitectureEvaluation,
    artifacts: tuple[CellStateArchitectureArtifact, ...],
) -> dict[str, object]:
    body = {
        "bundle_id": "d08-cell-state-architecture-bundle",
        "fixture_id": fixture.fixture_id,
        "evaluation_address": evaluation.content_address,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "artifact_addresses": tuple(item.content_address for item in artifacts),
        "accepted": evaluation.accepted and len(artifacts) == 6,
    }
    return body | {"content_address": addressed(body, "cell-state-bundle")}


__all__ = ["build_cell_state_architecture_bundle"]
