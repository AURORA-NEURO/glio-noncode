"""D10 release manifest construction."""

from __future__ import annotations

from .link_graph_architecture_contracts import (
    LinkGraphArchitectureArtifact,
    LinkGraphArchitectureEvaluation,
    LinkGraphArchitectureFixture,
    LinkGraphArchitectureRelease,
    LinkGraphArchitectureState,
    addressed,
)


def build_link_graph_architecture_release(
    fixture: LinkGraphArchitectureFixture,
    evaluation: LinkGraphArchitectureEvaluation,
    artifacts: tuple[LinkGraphArchitectureArtifact, ...],
) -> LinkGraphArchitectureRelease:
    body = {
        "release_id": "d10-link-graph-architecture-release",
        "fixture_id": fixture.fixture_id,
        "state": LinkGraphArchitectureState.PUBLISHED
        if evaluation.accepted and len(artifacts) == 6
        else LinkGraphArchitectureState.BLOCKED,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "provenance_address": addressed(fixture.sources, "link-provenance"),
        "limitations": (
            "public aggregate evidence only",
            "link association is descriptive and non-causal",
            "external calibration and clinical interpretation are out of scope",
        ),
    }
    return LinkGraphArchitectureRelease(**body, content_address=addressed(body, "link-release"))


def link_graph_architecture_release_manifest(
    release: LinkGraphArchitectureRelease,
) -> dict[str, object]:
    return release.to_dict()


__all__ = ["build_link_graph_architecture_release", "link_graph_architecture_release_manifest"]
