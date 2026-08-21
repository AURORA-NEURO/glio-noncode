"""Serializable evidence bundle for a C09-C12 run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import AtlasAlphaEvidenceEvaluationReport
from .atlas_alpha_evidence_lineage import AtlasAlphaEvidenceLineageReport
from .atlas_alpha_evidence_metrics import AtlasAlphaEvidenceMetrics
from .atlas_alpha_evidence_policy import AtlasAlphaEvidencePolicyReport
from .atlas_alpha_evidence_public_data import AtlasAlphaEvidenceDataAudit, AtlasAlphaEvidenceFixture
from .atlas_alpha_evidence_reconciliation import AtlasAlphaEvidenceReconciliationReport
from .atlas_alpha_evidence_replay import AtlasAlphaEvidenceReplayReport
from .atlas_alpha_evidence_scenario_matrix import AtlasAlphaEvidenceScenarioReport
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceBundle:
    """One immutable bundle joining all acceptance artifacts."""

    bundle_id: str
    bundle_version: str
    fixture: AtlasAlphaEvidenceFixture
    data_audit: AtlasAlphaEvidenceDataAudit
    evaluation: AtlasAlphaEvidenceEvaluationReport
    replay: AtlasAlphaEvidenceReplayReport
    scenarios: AtlasAlphaEvidenceScenarioReport
    policy: AtlasAlphaEvidencePolicyReport
    lineage: AtlasAlphaEvidenceLineageReport
    reconciliation: AtlasAlphaEvidenceReconciliationReport
    metrics: AtlasAlphaEvidenceMetrics
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.bundle_id, "bundle_id")
        require_non_empty(self.bundle_version, "bundle_version")
        require_non_empty(self.content_address, "content_address")

    @property
    def accepted(self) -> bool:
        return all(
            (
                self.data_audit.accepted,
                self.evaluation.accepted,
                self.replay.accepted,
                self.scenarios.accepted,
                self.policy.accepted,
                self.lineage.accepted,
                self.reconciliation.accepted,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_atlas_alpha_evidence_bundle(
    fixture: AtlasAlphaEvidenceFixture,
    data_audit: AtlasAlphaEvidenceDataAudit,
    evaluation: AtlasAlphaEvidenceEvaluationReport,
    replay: AtlasAlphaEvidenceReplayReport,
    scenarios: AtlasAlphaEvidenceScenarioReport,
    policy: AtlasAlphaEvidencePolicyReport,
    lineage: AtlasAlphaEvidenceLineageReport,
    reconciliation: AtlasAlphaEvidenceReconciliationReport,
    metrics: AtlasAlphaEvidenceMetrics,
) -> AtlasAlphaEvidenceBundle:
    """Assemble and address an evidence bundle."""

    body = {
        "bundle_id": "atlas-alpha-evidence-bundle",
        "bundle_version": "2026.08.d05-c09-c12.v1",
        "fixture": fixture,
        "data_audit": data_audit,
        "evaluation": evaluation,
        "replay": replay,
        "scenarios": scenarios,
        "policy": policy,
        "lineage": lineage,
        "reconciliation": reconciliation,
        "metrics": metrics,
    }
    return AtlasAlphaEvidenceBundle(**body, content_address=content_hash(body))


def write_atlas_alpha_evidence_bundle(bundle: AtlasAlphaEvidenceBundle, path: str) -> None:
    """Write a stable JSON bundle to a caller-selected path."""

    from pathlib import Path

    Path(path).write_text(
        __import__("json").dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "AtlasAlphaEvidenceBundle",
    "build_atlas_alpha_evidence_bundle",
    "write_atlas_alpha_evidence_bundle",
]
