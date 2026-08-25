"""Executable dependency-ordered plan for the whole-product gate."""

from __future__ import annotations

from .release_assurance_contracts import (
    RELEASE_ASSURANCE_PLAN_STEP_COUNT,
    ReleaseAssurancePlan,
    ReleaseAssurancePlanStep,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .serialization import content_hash

_PHASES = (
    ("source", "read the addressed service snapshot"),
    ("capability", "verify capability catalog certification"),
    ("architecture", "verify D01-D16 architecture readiness"),
    ("service", "verify service-release registry"),
    ("boundary", "verify repository public-surface audit"),
    ("evidence", "link cross-plane evidence addresses"),
    ("checks", "reconcile cross-plane checks"),
    ("summary", "publish readiness denominators"),
    ("runtime", "prepare staged replay runtime"),
    ("release", "close the whole-product release gate"),
)


def build_release_assurance_plan(snapshot: ReleaseAssuranceSnapshot) -> ReleaseAssurancePlan:
    """Build twenty explicit steps, two for every assurance phase."""

    steps: list[ReleaseAssurancePlanStep] = []
    check_ids = tuple(item.check_id for item in snapshot.checks)
    for index, (phase, action) in enumerate(_PHASES):
        for repeat in range(2):
            ordinal = index * 2 + repeat + 1
            selected = check_ids[(ordinal - 1) % len(check_ids)]
            body = {
                "ordinal": ordinal,
                "step_id": f"step:{ordinal:02d}:{phase}",
                "phase": phase,
                "action": action if repeat == 0 else f"{action} (close)",
                "inputs": (snapshot.content_address,) if ordinal == 1 else (f"step:{ordinal - 1:02d}",),
                "outputs": (f"release-assurance:{phase}:{repeat + 1}",),
                "check_ids": (selected,),
                "accepted": snapshot.accepted,
            }
            steps.append(ReleaseAssurancePlanStep(
                **body,
                content_address=content_hash(body, prefix="release-assurance-plan-step"),
            ))
    if len(steps) != RELEASE_ASSURANCE_PLAN_STEP_COUNT:
        raise ValueError("release-assurance plan denominator is not closed")
    body = {"bundle_id": snapshot.bundle_id, "steps": steps, "accepted": snapshot.accepted}
    return ReleaseAssurancePlan(
        snapshot.bundle_id,
        tuple(steps),
        snapshot.accepted,
        content_hash(body, prefix="release-assurance-plan"),
    )


def audit_release_assurance_plan(plan: ReleaseAssurancePlan) -> tuple:
    """Check plan order, identity, evidence linkage, and acceptance."""

    return (
        check("plan:count", "plan", ReleaseAssurancePlane.RUNTIME,
              len(plan.steps) == RELEASE_ASSURANCE_PLAN_STEP_COUNT, len(plan.steps),
              RELEASE_ASSURANCE_PLAN_STEP_COUNT, "plan closes the twenty-step denominator"),
        check("plan:ordinals", "plan", ReleaseAssurancePlane.RUNTIME,
              tuple(item.ordinal for item in plan.steps) == tuple(range(1, len(plan.steps) + 1)),
              tuple(item.ordinal for item in plan.steps[:3]), "contiguous one-based ordinals",
              "execution order is deterministic"),
        check("plan:identities", "plan", ReleaseAssurancePlane.RUNTIME,
              len({item.step_id for item in plan.steps}) == len(plan.steps),
              len({item.step_id for item in plan.steps}), len(plan.steps),
              "step identifiers are unique"),
        check("plan:evidence-links", "plan", ReleaseAssurancePlane.RUNTIME,
              all(item.check_ids for item in plan.steps),
              sum(bool(item.check_ids) for item in plan.steps), len(plan.steps),
              "every step carries a check reference"),
        check("plan:accepted", "plan", ReleaseAssurancePlane.RUNTIME,
              plan.accepted, plan.accepted, True, "accepted snapshot permits execution"),
    )


__all__ = ["audit_release_assurance_plan", "build_release_assurance_plan"]
