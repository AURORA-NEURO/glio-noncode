"""Executable release plan for the D01-D16 aggregate handoff."""

from __future__ import annotations

from .program_release_closure_contracts import (
    ProgramReleaseClosureCheck,
    ProgramReleaseClosurePlane,
    ProgramReleasePlan,
    ProgramReleasePlanStep,
    ProgramReleaseSnapshot,
    program_release_closure_check,
)
from .serialization import content_hash


def build_program_release_closure_plan(snapshot: ProgramReleaseSnapshot) -> ProgramReleasePlan:
    definitions = [
        (f"source-{domain.domain_id}", domain.domain_id, "project-source-domain")
        for domain in snapshot.domains
    ]
    definitions.extend(
        (
            ("aggregate-domains", "__program__", "assemble-domain-registry"),
            ("index-artifacts", "__program__", "index-portable-artifacts"),
            ("order-dependencies", "__program__", "materialize-dependency-dag"),
            ("evaluate-gates", "__program__", "evaluate-release-gates"),
            ("reconcile-release", "__program__", "reconcile-denominators"),
            ("certify-release", "__program__", "issue-domain-certificates"),
            ("publish-release", "__program__", "publish-public-projection"),
        )
    )
    steps: list[ProgramReleasePlanStep] = []
    for ordinal, (step_id, domain_id, action) in enumerate(definitions, start=1):
        prerequisites = (steps[-1].step_id,) if steps else ()
        if step_id.startswith("source-") and steps and steps[-1].step_id.startswith("source-"):
            prerequisites = ("source-" + snapshot.domains[ordinal - 2].domain_id,)
        body = {
            "step_id": step_id,
            "ordinal": ordinal,
            "domain_id": domain_id,
            "action": action,
            "prerequisite_ids": prerequisites,
            "input_address": snapshot.source_bundle_address
            if ordinal == 1
            else steps[-1].output_address
            if steps
            else snapshot.source_bundle_address,
            "output_address": snapshot.domains[ordinal - 1].content_address
            if step_id.startswith("source-")
            else snapshot.content_address,
            "accepted": snapshot.accepted,
        }
        steps.append(
            ProgramReleasePlanStep(
                **body, content_address=content_hash(body, prefix="program-release-plan-step")
            )
        )
    body = {"bundle_id": snapshot.bundle_id, "steps": tuple(steps), "accepted": snapshot.accepted}
    return ProgramReleasePlan(
        snapshot.bundle_id,
        tuple(steps),
        snapshot.accepted,
        content_hash(body, prefix="program-release-plan"),
    )


def audit_program_release_closure_plan(
    plan: ProgramReleasePlan,
) -> tuple[ProgramReleaseClosureCheck, ...]:
    checks = (
        program_release_closure_check(
            "plan:accepted",
            ProgramReleaseClosurePlane.PLAN,
            plan.accepted,
            plan.accepted,
            True,
            "plan follows snapshot acceptance",
        ),
        program_release_closure_check(
            "plan:step-count",
            ProgramReleaseClosurePlane.PLAN,
            len(plan.steps) == 23,
            len(plan.steps),
            23,
            "plan has sixteen source and seven closure steps",
        ),
        program_release_closure_check(
            "plan:ordinal-order",
            ProgramReleaseClosurePlane.PLAN,
            tuple(item.ordinal for item in plan.steps) == tuple(range(1, len(plan.steps) + 1)),
            tuple(item.ordinal for item in plan.steps),
            "contiguous ordinals",
            "plan ordinals are contiguous",
        ),
        program_release_closure_check(
            "plan:step-ids",
            ProgramReleaseClosurePlane.PLAN,
            len({item.step_id for item in plan.steps}) == len(plan.steps),
            len({item.step_id for item in plan.steps}),
            len(plan.steps),
            "plan step ids are unique",
        ),
        program_release_closure_check(
            "plan:addresses",
            ProgramReleaseClosurePlane.PLAN,
            all(item.input_address and item.output_address for item in plan.steps),
            sum(bool(item.input_address and item.output_address) for item in plan.steps),
            len(plan.steps),
            "all plan steps are addressed",
        ),
        program_release_closure_check(
            "plan:prerequisites",
            ProgramReleaseClosurePlane.PLAN,
            all(
                not item.prerequisite_ids
                or item.prerequisite_ids[0]
                in {step.step_id for step in plan.steps[: item.ordinal - 1]}
                for item in plan.steps
            ),
            True,
            True,
            "prerequisites point backwards",
        ),
    )
    return checks


def render_program_release_closure_plan(plan: ProgramReleasePlan) -> bytes:
    lines = [
        "# Program release closure plan",
        "",
        "| Ordinal | Step | Domain | Action | Prerequisites | Status |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.step_id} | {item.domain_id} | {item.action} | {', '.join(item.prerequisite_ids) or '—'} | {'accepted' if item.accepted else 'blocked'} |"
        for item in plan.steps
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = [
    name
    for name in globals()
    if name.startswith("build_program_release")
    or name.startswith("audit_program_release")
    or name.startswith("render_program_release")
    or name.startswith("ProgramRelease")
]
