"""Recovery plan for review, quarantine, and blocked release states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_policy import CohortFoundationDisposition, CohortFoundationPolicy
from .cohort_foundation_frontier_quality_gate import CohortFoundationQualityGate
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest


@dataclass(frozen=True, slots=True)
class CohortFoundationRecoveryStep:
    ordinal: int
    step_id: str
    trigger: str
    action: str
    required_receipt: str
    stop_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationRecoveryPlan:
    plan_id: str
    steps: tuple[CohortFoundationRecoveryStep, ...]
    review_count: int
    quarantine_count: int
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_recovery_plan(policy: CohortFoundationPolicy, quality: CohortFoundationQualityGate, release: CohortFoundationReleaseManifest) -> CohortFoundationRecoveryPlan:
    review_count = sum(item.disposition is CohortFoundationDisposition.REVIEW for item in policy.decisions)
    quarantine_count = sum(item.disposition is CohortFoundationDisposition.QUARANTINE for item in policy.decisions)
    definitions = (
        ("freeze-publish", "quality failure or release hold", "withhold descriptive export", quality.content_address, "do not publish until gate is accepted"),
        ("inspect-review", "review disposition exists", "inspect incomplete and absent inputs", policy.content_address, "retain issue codes and context"),
        ("confirm-quarantine", "foreign-context disposition exists", "confirm foreign records remain isolated", policy.content_address, "do not transport context"),
        ("replay-after-change", "source, threshold, or schema changes", "re-run deterministic fixture replay", release.content_address, "stop on changed record address"),
        ("rebuild-release", "all blocking checks pass", "rebuild bundle and manifest", quality.content_address, "release only aggregate research output"),
    )
    steps = tuple(CohortFoundationRecoveryStep(index, step_id, trigger, action, receipt, stop, content_hash((step_id, trigger, action, receipt, stop))) for index, (step_id, trigger, action, receipt, stop) in enumerate(definitions, start=1))
    body = {"plan_id": "cohort-foundation-frontier-recovery", "steps": steps, "review_count": review_count, "quarantine_count": quarantine_count, "quality": quality.accepted}
    return CohortFoundationRecoveryPlan(body["plan_id"], steps, review_count, quarantine_count, len(steps) == 5 and review_count > 0 and quarantine_count > 0, content_hash(body))


__all__ = ["CohortFoundationRecoveryPlan", "CohortFoundationRecoveryStep", "build_cohort_foundation_frontier_recovery_plan"]
