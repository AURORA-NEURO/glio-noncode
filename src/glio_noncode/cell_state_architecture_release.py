"""Release gating and limitation statements for D08."""

from __future__ import annotations

from .cell_state_architecture_artifacts import artifacts_are_review_safe
from .cell_state_architecture_contracts import (
    CELL_STATE_ARCHITECTURE_VERSION,
    CellStateArchitectureArtifact,
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    CellStateArchitectureRelease,
    CellStateArchitectureState,
    addressed,
)

D08_LIMITATIONS = (
    "public aggregate evidence only",
    "no subject-level inference or treatment recommendation",
    "foreign context and identity conflict controls remain held",
    "cell-state publication requires all three upstream receipts",
)


def build_cell_state_architecture_release(
    fixture: CellStateArchitectureFixture,
    evaluation: CellStateArchitectureEvaluation,
    artifacts: tuple[CellStateArchitectureArtifact, ...],
) -> CellStateArchitectureRelease:
    accepted = evaluation.accepted and artifacts_are_review_safe(artifacts)
    state = CellStateArchitectureState.PUBLISHED if accepted else CellStateArchitectureState.BLOCKED
    body = {
        "release_id": "d08-cell-state-architecture-release",
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "provenance_address": addressed(
            {"fixture": fixture.content_address, "version": CELL_STATE_ARCHITECTURE_VERSION},
            "cell-state-provenance",
        ),
        "limitations": D08_LIMITATIONS,
    }
    return CellStateArchitectureRelease(
        **body, content_address=addressed(body, "cell-state-release")
    )


def release_manifest(release: CellStateArchitectureRelease) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "fixture_id": release.fixture_id,
        "state": release.state.value,
        "artifact_ids": list(release.artifact_ids),
        "provenance_address": release.provenance_address,
        "limitations": list(release.limitations),
        "content_address": release.content_address,
    }


__all__ = ["D08_LIMITATIONS", "build_cell_state_architecture_release", "release_manifest"]
