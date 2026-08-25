"""Dependency-ordered promotion plan for the service-release registry."""

from __future__ import annotations

from .service_release_contracts import (
    SERVICE_RELEASE_PLAN_STEP_COUNT,
    ServiceReleasePlan,
    ServiceReleasePlanStep,
    ServiceReleasePlane,
    ServiceReleaseSnapshot,
    check,
)
from .serialization import content_hash

_PHASES = (
    ("intake", "read the addressed service snapshot"),
    ("inventory", "register public service surfaces"),
    ("projection", "materialize exact public projections"),
    ("lineage", "close surface dependencies"),
    ("gates", "evaluate acceptance gates"),
    ("indexes", "build address-only indexes"),
    ("reconciliation", "reconcile source and release denominators"),
    ("certification", "run independent certification checks"),
    ("observability", "publish deterministic events and metrics"),
    ("graph", "connect release lineage"),
    ("negative-controls", "run failure injections"),
    ("review", "prepare reviewer views"),
    ("release", "close export and replay gates"),
)


def build_service_release_plan(snapshot: ServiceReleaseSnapshot) -> ServiceReleasePlan:
    """Build 23 explicit steps with inputs, outputs, and gate references."""

    steps: list[ServiceReleasePlanStep] = []
    ordinal = 0
    for phase, action in _PHASES:
        repeats = 1 if phase in {"intake", "graph", "release"} else 2
        for repeat in range(repeats):
            ordinal += 1
            step_id = f"step:{ordinal:02d}:{phase}"
            inputs = (snapshot.content_address,) if ordinal == 1 else (f"step:{ordinal - 1:02d}:{_PHASES[0][0] if ordinal == 2 else phase}",)
            outputs = (f"service-release:{phase}:{repeat + 1}",)
            gate_ids = tuple(
                item.gate_id
                for item in snapshot.gates
                if item.surface_id == snapshot.surfaces[(ordinal - 1) % len(snapshot.surfaces)].surface_id
            )[:2]
            body = {
                "ordinal": ordinal,
                "step_id": step_id,
                "phase": phase,
                "action": action if repeats == 1 else f"{action} ({repeat + 1})",
                "inputs": inputs,
                "outputs": outputs,
                "gate_ids": gate_ids,
                "accepted": snapshot.accepted,
            }
            steps.append(ServiceReleasePlanStep(
                **body, content_address=content_hash(body, prefix="service-release-plan-step")
            ))
    if len(steps) != SERVICE_RELEASE_PLAN_STEP_COUNT:
        raise ValueError("service release plan denominator is not closed")
    body = {"bundle_id": snapshot.bundle_id, "steps": steps, "accepted": snapshot.accepted}
    return ServiceReleasePlan(
        snapshot.bundle_id, tuple(steps), snapshot.accepted,
        content_hash(body, prefix="service-release-plan"),
    )


def audit_service_release_plan(plan: ServiceReleasePlan) -> tuple:
    """Check contiguous ordinals, unique steps, and acceptance propagation."""

    return (
        check("plan:count", ServiceReleasePlane.PLAN,
              len(plan.steps) == SERVICE_RELEASE_PLAN_STEP_COUNT, len(plan.steps),
              SERVICE_RELEASE_PLAN_STEP_COUNT, "plan contains the closed step denominator"),
        check("plan:ordinals", ServiceReleasePlane.PLAN,
              tuple(item.ordinal for item in plan.steps) == tuple(range(1, len(plan.steps) + 1)),
              tuple(item.ordinal for item in plan.steps[:3]), "contiguous one-based ordinals",
              "plan execution order is deterministic"),
        check("plan:identities", ServiceReleasePlane.PLAN,
              len({item.step_id for item in plan.steps}) == len(plan.steps),
              len({item.step_id for item in plan.steps}), len(plan.steps),
              "plan step identifiers are unique"),
        check("plan:gates", ServiceReleasePlane.PLAN,
              all(item.gate_ids for item in plan.steps),
              sum(bool(item.gate_ids) for item in plan.steps), len(plan.steps),
              "every plan step is linked to promotion evidence"),
        check("plan:accepted", ServiceReleasePlane.PLAN, plan.accepted,
              plan.accepted, True, "accepted snapshot permits the release plan"),
    )


__all__ = ["audit_service_release_plan", "build_service_release_plan"]
