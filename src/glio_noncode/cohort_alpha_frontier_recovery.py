"""Recovery playbooks for bounded C09-C12 publication failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_failure_injection import CohortAlphaFrontierFailureReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRecoveryStep:
    step_id: str
    order: int
    action: str
    gate: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRecoveryPlan:
    plan_id: str
    steps: tuple[CohortAlphaFrontierRecoveryStep, ...]
    failure_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_recovery_plan(report: CohortAlphaFrontierFailureReport) -> CohortAlphaFrontierRecoveryPlan:
    raw = (("freeze", "freeze publication", "policy"), ("replay", "replay the immutable fixture", "replay"), ("reconcile", "reconcile expected and observed states", "reconciliation"), ("repair", "apply the case repair receipt", "source_or_identity"), ("recheck", "rerun all quality checks", "quality"), ("release", "release only if every gate is accepted", "manifest"))
    steps = tuple(CohortAlphaFrontierRecoveryStep(f"recovery-{index:02d}-{step_id}", index, action, gate, step_id != "release", content_hash({"step_id": step_id, "order": index, "action": action, "gate": gate}, prefix="alpha-recovery-step")) for index, (step_id, action, gate) in enumerate(raw, 1))
    return CohortAlphaFrontierRecoveryPlan("cohort-alpha-frontier-recovery", steps, sum(item.blocked for item in report.assessments), report.accepted and len(steps) == 6 and tuple(item.order for item in steps) == tuple(range(1, 7)), content_hash({"steps": steps, "failure_count": sum(item.blocked for item in report.assessments)}, prefix="alpha-recovery"))


__all__ = ["CohortAlphaFrontierRecoveryPlan", "CohortAlphaFrontierRecoveryStep", "build_cohort_alpha_frontier_recovery_plan"]
