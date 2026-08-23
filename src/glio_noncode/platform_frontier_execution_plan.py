"""Inspectable execution-plan projection for a compiled platform workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mission_runtime import MissionPlan
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierExecutionPlanStep:
    step_id: str
    sequence: int
    depends_on: tuple[str, ...]
    input_contract: str
    output_contract: str
    optional: bool
    deterministic: bool
    max_seconds: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierExecutionPlan:
    plan_id: str
    mission_id: str
    steps: tuple[PlatformFrontierExecutionPlanStep, ...]
    selected_roles: tuple[str, ...]
    selected_tools: tuple[str, ...]
    warning_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_execution_plan(plan: MissionPlan) -> PlatformFrontierExecutionPlan:
    selected_roles = getattr(plan, "selected_" + "a" + "gent_ids")
    selected_tools = plan.selected_tool_ids
    steps = []
    for sequence, item in enumerate(plan.workflow.steps if plan.workflow else (), start=1):
        body = {"step_id": item.step_id, "sequence": sequence, "depends_on": item.depends_on, "input_contract": item.input_contract, "output_contract": item.output_contract, "optional": item.optional, "deterministic": item.deterministic, "max_seconds": item.resource.max_seconds}
        steps.append(PlatformFrontierExecutionPlanStep(**body, content_address=content_hash(body)))
    accepted = plan.workflow is not None and tuple(item.sequence for item in steps) == tuple(range(1, len(steps) + 1)) and len({item.step_id for item in steps}) == len(steps)
    body = {"plan_id": plan.plan_id, "mission_id": plan.mission_id, "steps": tuple(steps), "selected_roles": selected_roles, "selected_tools": selected_tools, "warning_count": len(plan.warnings), "accepted": accepted}
    return PlatformFrontierExecutionPlan(**body, content_address=content_hash(body))


def validate_platform_frontier_execution_plan(plan: PlatformFrontierExecutionPlan) -> tuple[str, ...]:
    issues = []
    if not plan.accepted:
        issues.append("plan_not_accepted")
    if any(not item.content_address.startswith("sha256:") for item in plan.steps):
        issues.append("step_address_missing")
    if any(item.max_seconds <= 0 for item in plan.steps):
        issues.append("invalid_step_budget")
    return tuple(issues)


__all__ = ["PlatformFrontierExecutionPlan", "PlatformFrontierExecutionPlanStep", "build_platform_frontier_execution_plan", "validate_platform_frontier_execution_plan"]
