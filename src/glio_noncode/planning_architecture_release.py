"""D13 publication decision and limitation boundary."""

from __future__ import annotations

from .planning_architecture_artifacts import planning_architecture_artifacts_are_safe
from .planning_architecture_contracts import (
    PlanningArchitectureArtifact,
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    PlanningArchitectureRelease,
    PlanningArchitectureState,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture

_LIMITATIONS = (
    "public aggregate receipts and synthetic planning payloads only",
    "planning states do not establish assay efficacy or biological causality",
    "held, blocked, rejected, and abstained paths remain visible",
    "external review and institutional controls remain outside this release",
)


def build_planning_architecture_release(
    fixture: PlanningArchitectureFixture | None = None,
    evaluation: PlanningArchitectureEvaluation | None = None,
    artifacts: tuple[PlanningArchitectureArtifact, ...] = (),
) -> PlanningArchitectureRelease:
    selected = fixture or default_planning_architecture_fixture()
    if evaluation is None:
        from .planning_architecture_operations import evaluate_planning_architecture_fixture

        evaluation = evaluate_planning_architecture_fixture(selected)
    safe = planning_architecture_artifacts_are_safe(artifacts)
    published = evaluation.accepted and safe
    state = PlanningArchitectureState.PUBLISHED if published else PlanningArchitectureState.REVIEW
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    body = {
        "release_id": "planning-architecture-release-001",
        "fixture_id": selected.fixture_id,
        "state": state,
        "artifact_ids": artifact_ids,
        "provenance_address": addressed(
            {
                "fixture": selected.content_address,
                "evaluation": evaluation.content_address,
                "artifacts": artifact_ids,
            },
            "planning-provenance",
        ),
        "limitations": _LIMITATIONS,
    }
    return PlanningArchitectureRelease(
        **body,
        content_address=addressed(body, "planning-release"),
    )


def planning_architecture_release_is_publishable(
    release: PlanningArchitectureRelease,
) -> bool:
    return release.state is PlanningArchitectureState.PUBLISHED and bool(release.limitations)


def planning_architecture_release_summary(
    release: PlanningArchitectureRelease,
) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "fixture_id": release.fixture_id,
        "state": release.state.value,
        "publishable": planning_architecture_release_is_publishable(release),
        "artifact_count": len(release.artifact_ids),
        "limitation_count": len(release.limitations),
    }


__all__ = [
    "build_planning_architecture_release",
    "planning_architecture_release_is_publishable",
    "planning_architecture_release_summary",
]
