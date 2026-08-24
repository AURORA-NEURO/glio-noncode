"""Release decision and limitations for D16."""

from __future__ import annotations

from .platform_execution_architecture_artifacts import platform_execution_artifacts_are_safe
from .platform_execution_architecture_contracts import (
    PlatformExecutionArtifact,
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    PlatformExecutionRelease,
    PlatformExecutionState,
    addressed,
)
from .platform_execution_architecture_public_data import default_platform_execution_fixture

_LIMITATIONS = (
    "public aggregate execution receipts and bounded control projections only",
    "platform states do not establish clinical efficacy or causal conclusions",
    "blocked, denied, rejected, abstained, drift, and hold paths remain visible",
    "external security review and institutional controls remain outside this release",
)


def build_platform_execution_release(
    fixture: PlatformExecutionFixture | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
    artifacts: tuple[PlatformExecutionArtifact, ...] = (),
) -> PlatformExecutionRelease:
    selected = fixture or default_platform_execution_fixture()
    if evaluation is None:
        from .platform_execution_architecture_operations import evaluate_platform_execution_fixture

        evaluation = evaluate_platform_execution_fixture(selected)
    published = evaluation.accepted and platform_execution_artifacts_are_safe(artifacts)
    state = PlatformExecutionState.PUBLISHED if published else PlatformExecutionState.REVIEW
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    body = {
        "release_id": "platform-execution-release-001",
        "fixture_id": selected.fixture_id,
        "state": state,
        "artifact_ids": artifact_ids,
        "provenance_address": addressed(
            {
                "fixture": selected.content_address,
                "evaluation": evaluation.content_address,
                "artifacts": artifact_ids,
            },
            "platform-execution-provenance",
        ),
        "limitations": _LIMITATIONS,
    }
    return PlatformExecutionRelease(
        **body, content_address=addressed(body, "platform-execution-release")
    )


def platform_execution_release_is_publishable(release: PlatformExecutionRelease) -> bool:
    return release.state is PlatformExecutionState.PUBLISHED and bool(release.limitations)


__all__ = ["build_platform_execution_release", "platform_execution_release_is_publishable"]
