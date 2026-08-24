"""Publication decision and limitation boundary for D15."""

from __future__ import annotations

from .workbench_architecture_artifacts import workbench_architecture_artifacts_are_safe
from .workbench_architecture_contracts import (
    WorkbenchArchitectureArtifact,
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureRelease,
    WorkbenchArchitectureState,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture

_LIMITATIONS = (
    "public aggregate workbench receipts and bounded views only",
    "workspace states do not establish assay efficacy, causality, or clinical decisions",
    "held, blocked, denied, rejected, and abstained paths remain visible",
    "external review and institutional controls remain outside this release",
)


def build_workbench_architecture_release(
    fixture: WorkbenchArchitectureFixture | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
    artifacts: tuple[WorkbenchArchitectureArtifact, ...] = (),
) -> WorkbenchArchitectureRelease:
    selected = fixture or default_workbench_architecture_fixture()
    if evaluation is None:
        from .workbench_architecture_operations import evaluate_workbench_architecture_fixture

        evaluation = evaluate_workbench_architecture_fixture(selected)
    published = evaluation.accepted and workbench_architecture_artifacts_are_safe(artifacts)
    state = WorkbenchArchitectureState.PUBLISHED if published else WorkbenchArchitectureState.REVIEW
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    body = {
        "release_id": "workbench-architecture-release-001",
        "fixture_id": selected.fixture_id,
        "state": state,
        "artifact_ids": artifact_ids,
        "provenance_address": addressed(
            {
                "fixture": selected.content_address,
                "evaluation": evaluation.content_address,
                "artifacts": artifact_ids,
            },
            "workbench-architecture-provenance",
        ),
        "limitations": _LIMITATIONS,
    }
    return WorkbenchArchitectureRelease(
        **body, content_address=addressed(body, "workbench-architecture-release")
    )


def workbench_architecture_release_is_publishable(release: WorkbenchArchitectureRelease) -> bool:
    return release.state is WorkbenchArchitectureState.PUBLISHED and bool(release.limitations)


def workbench_architecture_release_summary(
    release: WorkbenchArchitectureRelease,
) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "fixture_id": release.fixture_id,
        "state": release.state.value,
        "publishable": workbench_architecture_release_is_publishable(release),
        "artifact_count": len(release.artifact_ids),
        "limitation_count": len(release.limitations),
    }


__all__ = [
    "build_workbench_architecture_release",
    "workbench_architecture_release_is_publishable",
    "workbench_architecture_release_summary",
]
