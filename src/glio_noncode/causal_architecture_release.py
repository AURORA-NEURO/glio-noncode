"""D11 release manifest construction."""

from __future__ import annotations

from .causal_architecture_contracts import (
    CausalArchitectureArtifact,
    CausalArchitectureEvaluation,
    CausalArchitectureFixture,
    CausalArchitectureRelease,
    CausalArchitectureState,
    addressed,
)


def build_causal_architecture_release(
    fixture: CausalArchitectureFixture,
    evaluation: CausalArchitectureEvaluation,
    artifacts: tuple[CausalArchitectureArtifact, ...],
) -> CausalArchitectureRelease:
    body = {
        "release_id": "d11-causal-architecture-release",
        "fixture_id": fixture.fixture_id,
        "state": CausalArchitectureState.PUBLISHED
        if evaluation.accepted and len(artifacts) == 6
        else CausalArchitectureState.BLOCKED,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "provenance_address": addressed(fixture.sources, "causal-provenance"),
        "limitations": (
            "public aggregate evidence only",
            "scores are bounded research proxies",
            "no causal identification, clinical effect, or treatment decision is established",
        ),
    }
    return CausalArchitectureRelease(**body, content_address=addressed(body, "causal-release"))


def causal_architecture_release_manifest(release: CausalArchitectureRelease) -> dict[str, object]:
    return release.to_dict()


__all__ = ["build_causal_architecture_release", "causal_architecture_release_manifest"]
