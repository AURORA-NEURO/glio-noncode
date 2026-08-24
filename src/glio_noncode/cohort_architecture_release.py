"""D12 published release manifest and limitation ceiling."""

from __future__ import annotations

from .cohort_architecture_contracts import (
    CohortArchitectureArtifact,
    CohortArchitectureEvaluation,
    CohortArchitectureFixture,
    CohortArchitectureRelease,
    CohortArchitectureState,
    addressed,
)


def build_cohort_architecture_release(
    fixture: CohortArchitectureFixture,
    evaluation: CohortArchitectureEvaluation,
    artifacts: tuple[CohortArchitectureArtifact, ...],
) -> CohortArchitectureRelease:
    limitations = (
        "public aggregate research evidence only",
        "cohort composition, callable space, phase coverage, and source dependence remain material",
        (
            "descriptive recurrence, convergence, longitudinal, fairness, transport, "
            "and discovery outputs are not clinical evidence"
        ),
        "context transfer and causal interpretation require external validation",
    )
    body = {
        "release_id": "cohort-architecture-d12-release",
        "fixture_id": fixture.fixture_id,
        "state": CohortArchitectureState.PUBLISHED,
        "artifact_ids": tuple(item.artifact_id for item in artifacts),
        "provenance_address": addressed(
            (fixture.content_address, evaluation.content_address), "cohort-provenance"
        ),
        "limitations": limitations,
    }
    state = (
        CohortArchitectureState.PUBLISHED
        if evaluation.accepted and len(artifacts) == 6
        else CohortArchitectureState.REVIEW
    )
    return CohortArchitectureRelease(
        **(body | {"state": state}),
        content_address=addressed(body | {"state": state}, "cohort-release"),
    )


def cohort_architecture_release_manifest(
    release: CohortArchitectureRelease,
) -> dict[str, object]:
    return release.to_dict()


__all__ = ["build_cohort_architecture_release", "cohort_architecture_release_manifest"]
