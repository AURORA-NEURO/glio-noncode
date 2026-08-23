"""Release boundary for public aggregate topology evidence."""

from __future__ import annotations

from .topology_architecture_artifacts import topology_architecture_artifacts_are_safe
from .topology_architecture_contracts import (
    TopologyArchitectureArtifact,
    TopologyArchitectureEvaluation,
    TopologyArchitectureFixture,
    TopologyArchitectureRelease,
    TopologyArchitectureState,
    addressed,
)

TOPOLOGY_ARCHITECTURE_LIMITATIONS = (
    "public aggregate topology evidence only",
    "contact and boundary outputs remain descriptive",
    "SV rewiring is a declared simulation, not a prediction",
    "foreign, malformed, and identity controls remain review-held",
    "3D publication requires the exact aggregate context",
)


def build_topology_architecture_release(
    fixture: TopologyArchitectureFixture,
    evaluation: TopologyArchitectureEvaluation,
    artifacts: tuple[TopologyArchitectureArtifact, ...],
) -> TopologyArchitectureRelease:
    accepted = evaluation.accepted and topology_architecture_artifacts_are_safe(artifacts)
    state = TopologyArchitectureState.PUBLISHED if accepted else TopologyArchitectureState.BLOCKED
    body = {
        "release_id": "d09-topology-architecture-release",
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "provenance_address": addressed(
            {"fixture": fixture.content_address, "evaluation": evaluation.content_address},
            "topology-provenance",
        ),
        "limitations": TOPOLOGY_ARCHITECTURE_LIMITATIONS,
    }
    return TopologyArchitectureRelease(**body, content_address=addressed(body, "topology-release"))


def topology_architecture_release_manifest(
    release: TopologyArchitectureRelease,
) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "fixture_id": release.fixture_id,
        "state": release.state.value,
        "artifact_ids": list(release.artifact_ids),
        "limitations": list(release.limitations),
        "content_address": release.content_address,
    }


__all__ = [
    "TOPOLOGY_ARCHITECTURE_LIMITATIONS",
    "build_topology_architecture_release",
    "topology_architecture_release_manifest",
]
