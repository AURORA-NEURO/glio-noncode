"""Recovery actions for held, reviewed, or quarantined rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_policy import CohortBetaFrontierDisposition, CohortBetaFrontierPolicy
from .cohort_beta_frontier_quality_gate import CohortBetaFrontierQualityGate
from .cohort_beta_frontier_release import CohortBetaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRecoveryAction:
    action_id: str
    trigger: str
    action: str
    exit_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRecoveryPlan:
    actions: tuple[CohortBetaFrontierRecoveryAction, ...]
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_recovery_plan(policy: CohortBetaFrontierPolicy, quality: CohortBetaFrontierQualityGate, release: CohortBetaFrontierReleaseManifest) -> CohortBetaFrontierRecoveryPlan:
    actions = [CohortBetaFrontierRecoveryAction("review-partial", "partial disposition", "obtain comparator or retain partial state", "review receipt is attached", content_hash("review-partial", prefix="recovery")), CohortBetaFrontierRecoveryAction("quarantine-foreign", "foreign context", "exclude from target-context aggregation", "context key is reconciled", content_hash("quarantine-foreign", prefix="recovery")), CohortBetaFrontierRecoveryAction("hold-release", "quality or replay failure", "hold manifest and re-run checks", "quality and replay are accepted", content_hash("hold-release", prefix="recovery"))]
    return CohortBetaFrontierRecoveryPlan(tuple(actions), bool(actions) and (quality.accepted or not release.ready), content_hash(actions, prefix="recovery-plan"))


__all__ = ["CohortBetaFrontierRecoveryAction", "CohortBetaFrontierRecoveryPlan", "build_cohort_beta_frontier_recovery_plan"]
