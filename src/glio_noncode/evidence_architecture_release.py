"""Publication decision and limitation boundary for D14."""

from __future__ import annotations

from .evidence_architecture_artifacts import evidence_architecture_artifacts_are_safe
from .evidence_architecture_contracts import (
    EvidenceArchitectureArtifact,
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureFixture,
    EvidenceArchitectureRelease,
    EvidenceArchitectureState,
    addressed,
)
from .evidence_architecture_public_data import default_evidence_architecture_fixture

_LIMITATIONS = (
    "public aggregate receipts and bounded delegate payloads only",
    "lifecycle states do not establish assay efficacy or biological causality",
    "held, blocked, rejected, and abstained paths remain visible",
    "external review and institutional controls remain outside this release",
)


def build_evidence_architecture_release(
    fixture: EvidenceArchitectureFixture | None = None,
    evaluation: EvidenceArchitectureEvaluation | None = None,
    artifacts: tuple[EvidenceArchitectureArtifact, ...] = (),
) -> EvidenceArchitectureRelease:
    selected = fixture or default_evidence_architecture_fixture()
    if evaluation is None:
        from .evidence_architecture_operations import evaluate_evidence_architecture_fixture

        evaluation = evaluate_evidence_architecture_fixture(selected)
    published = evaluation.accepted and evidence_architecture_artifacts_are_safe(artifacts)
    state = EvidenceArchitectureState.PUBLISHED if published else EvidenceArchitectureState.REVIEW
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    body = {
        "release_id": "evidence-architecture-release-001",
        "fixture_id": selected.fixture_id,
        "state": state,
        "artifact_ids": artifact_ids,
        "provenance_address": addressed(
            {
                "fixture": selected.content_address,
                "evaluation": evaluation.content_address,
                "artifacts": artifact_ids,
            },
            "evidence-architecture-provenance",
        ),
        "limitations": _LIMITATIONS,
    }
    return EvidenceArchitectureRelease(
        **body, content_address=addressed(body, "evidence-architecture-release")
    )


def evidence_architecture_release_is_publishable(
    release: EvidenceArchitectureRelease,
) -> bool:
    return release.state is EvidenceArchitectureState.PUBLISHED and bool(release.limitations)


def evidence_architecture_release_summary(
    release: EvidenceArchitectureRelease,
) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "fixture_id": release.fixture_id,
        "state": release.state.value,
        "publishable": evidence_architecture_release_is_publishable(release),
        "artifact_count": len(release.artifact_ids),
        "limitation_count": len(release.limitations),
    }


__all__ = [
    "build_evidence_architecture_release",
    "evidence_architecture_release_is_publishable",
    "evidence_architecture_release_summary",
]
