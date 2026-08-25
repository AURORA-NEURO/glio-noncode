"""Deterministic execution plan for assembling the D13-D16 release."""

from __future__ import annotations

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FrontierReleasePlan,
    FrontierReleasePlanStep,
)
from .serialization import content_hash

_PLAN = (
    ("source-d13", "D13", "materialize validation-design closure", ()),
    ("source-d14", "D14", "materialize evidence-lifecycle closure", ("source-d13",)),
    ("source-d15", "D15", "materialize workbench-release closure", ("source-d14",)),
    ("source-d16", "D16", "materialize deployment-frontier closure", ("source-d15",)),
    (
        "aggregate-domains",
        "release",
        "aggregate four domain closure receipts",
        ("source-d13", "source-d14", "source-d15", "source-d16"),
    ),
    ("index-artifacts", "release", "build namespaced artifact indexes", ("aggregate-domains",)),
    (
        "order-dependencies",
        "release",
        "build forward release dependency matrix",
        ("aggregate-domains",),
    ),
    (
        "evaluate-gates",
        "release",
        "evaluate six release gates per domain",
        ("index-artifacts", "order-dependencies"),
    ),
    ("reconcile-release", "release", "reconcile cross-domain denominators", ("evaluate-gates",)),
    ("certify-release", "release", "issue eight-domain certification", ("reconcile-release",)),
    ("observe-release", "release", "emit release events and metrics", ("certify-release",)),
    (
        "graph-release",
        "release",
        "connect domains, artifacts, gates, and dependencies",
        ("observe-release",),
    ),
    ("publish-release", "release", "finalize exact-byte release export", ("graph-release",)),
)


def build_frontier_release_plan(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleasePlan:
    addresses: dict[str, str] = {"root": snapshot.content_address}
    steps: list[FrontierReleasePlanStep] = []
    for ordinal, (step_id, domain_id, action, prerequisites) in enumerate(_PLAN, 1):
        input_address = content_hash(
            {
                "step_id": step_id,
                "prerequisites": tuple(addresses.get(item, "") for item in prerequisites),
            },
            prefix="frontier-release-plan-input",
        )
        accepted = snapshot.accepted and all(
            prerequisite in addresses for prerequisite in prerequisites
        )
        output_address = content_hash(
            {
                "step_id": step_id,
                "ordinal": ordinal,
                "domain_id": domain_id,
                "action": action,
                "input_address": input_address,
                "accepted": accepted,
            },
            prefix="frontier-release-plan-output",
        )
        body = {
            "step_id": step_id,
            "ordinal": ordinal,
            "domain_id": domain_id,
            "action": action,
            "prerequisite_ids": prerequisites,
            "input_address": input_address,
            "output_address": output_address,
            "accepted": accepted,
        }
        step = FrontierReleasePlanStep(
            **body,
            content_address=content_hash(body, prefix="frontier-release-plan-step"),
        )
        steps.append(step)
        addresses[step_id] = step.output_address
    body = {
        "bundle_id": snapshot.bundle_id,
        "steps": tuple(steps),
        "accepted": len(steps) == len(_PLAN) and all(item.accepted for item in steps),
    }
    return FrontierReleasePlan(
        **body,
        content_address=content_hash(body, prefix="frontier-release-plan"),
    )


def audit_frontier_release_plan(plan: FrontierReleasePlan) -> tuple[dict[str, object], ...]:
    step_ids = tuple(item.step_id for item in plan.steps)
    checks = (
        {
            "check_id": "plan-count",
            "passed": len(plan.steps) == len(_PLAN),
            "observed": len(plan.steps),
            "expected": len(_PLAN),
        },
        {
            "check_id": "plan-identity",
            "passed": len(step_ids) == len(set(step_ids)),
            "observed": len(set(step_ids)),
            "expected": len(step_ids),
        },
        {
            "check_id": "plan-order",
            "passed": tuple(item.ordinal for item in plan.steps)
            == tuple(range(1, len(plan.steps) + 1)),
            "observed": tuple(item.ordinal for item in plan.steps),
            "expected": tuple(range(1, len(plan.steps) + 1)),
        },
        {
            "check_id": "plan-prerequisites",
            "passed": all(
                all(prerequisite in step_ids for prerequisite in item.prerequisite_ids)
                for item in plan.steps
            ),
            "observed": True,
            "expected": True,
        },
        {
            "check_id": "plan-addresses",
            "passed": all(
                item.input_address and item.output_address and item.content_address
                for item in plan.steps
            ),
            "observed": True,
            "expected": True,
        },
        {
            "check_id": "plan-accepted",
            "passed": plan.accepted,
            "observed": plan.accepted,
            "expected": True,
        },
    )
    return tuple(checks)


def frontier_release_plan_markdown(plan: FrontierReleasePlan) -> str:
    lines = [
        "# Frontier release plan",
        "",
        f"Bundle: `{plan.bundle_id}`",
        f"Accepted: `{str(plan.accepted).lower()}`",
        "",
        "| Ordinal | Step | Domain | Action | Prerequisites | State |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.step_id}` | `{item.domain_id}` | {item.action} | "
        f"{', '.join(item.prerequisite_ids) or '—'} | `{'ready' if item.accepted else 'blocked'}` |"
        for item in plan.steps
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "audit_frontier_release_plan",
    "build_frontier_release_plan",
    "frontier_release_plan_markdown",
]
