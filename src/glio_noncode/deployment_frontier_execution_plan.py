"""Explicit execution plan for deployment governance runtime stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierExecutionPlanStep:
    step_id: str
    sequence: int
    depends_on: tuple[str, ...]
    input_kind: str
    output_kind: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierExecutionPlan:
    plan_id: str
    steps: tuple[DeploymentFrontierExecutionPlanStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_execution_plan(*, plan_id: str = "deployment-frontier-plan") -> DeploymentFrontierExecutionPlan:
    rows = (("data-audit", (), "fixture", "audit"), ("evaluation", ("data-audit",), "audit", "evaluation"), ("quality", ("evaluation",), "evaluation", "quality"), ("release", ("quality",), "quality", "release"), ("package", ("release",), "release", "bundle"))
    steps = []
    for sequence, (step_id, depends_on, input_kind, output_kind) in enumerate(rows, start=1):
        body = {"step_id": step_id, "sequence": sequence, "depends_on": depends_on, "input_kind": input_kind, "output_kind": output_kind, "required": True}
        steps.append(DeploymentFrontierExecutionPlanStep(**body, content_address=deployment_address(body)))
    return DeploymentFrontierExecutionPlan(plan_id, tuple(steps), tuple(item.sequence for item in steps) == tuple(range(1, len(steps) + 1)), deployment_address(tuple(steps)))


def validate_deployment_frontier_execution_plan(plan: DeploymentFrontierExecutionPlan) -> tuple[str, ...]:
    ids = {item.step_id for item in plan.steps}
    issues = ["sequence_gap"] if tuple(item.sequence for item in plan.steps) != tuple(range(1, len(plan.steps) + 1)) else []
    issues.extend(f"missing_dependency:{dependency}" for item in plan.steps for dependency in item.depends_on if dependency not in ids)
    return tuple(issues)


__all__ = ["DeploymentFrontierExecutionPlan", "DeploymentFrontierExecutionPlanStep", "build_deployment_frontier_execution_plan", "validate_deployment_frontier_execution_plan"]
