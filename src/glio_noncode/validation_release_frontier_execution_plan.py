"""Dependency-safe execution plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleasePlanStep:
    step_id: str
    depends_on: tuple[str, ...]
    output_kind: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseExecutionPlan:
    steps: tuple[ValidationReleasePlanStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_execution_plan() -> ValidationReleaseExecutionPlan:
    raw = (("data-audit", (), "audit"), ("adapters", ("data-audit",), "adapter"), ("evaluation", ("adapters",), "evaluation"), ("metrics", ("evaluation",), "metrics"), ("quality", ("metrics",), "quality"), ("release", ("quality",), "release"), ("handoff", ("release",), "handoff"))
    steps = []
    for step_id, depends_on, output_kind in raw:
        body = {"step_id": step_id, "depends_on": depends_on, "output_kind": output_kind}
        steps.append(ValidationReleasePlanStep(**body, content_address=content_hash(body)))
    return ValidationReleaseExecutionPlan(tuple(steps), True, content_hash(tuple(steps)))


def validate_validation_release_execution_plan(plan: ValidationReleaseExecutionPlan) -> tuple[str, ...]:
    seen = set()
    errors = []
    for step in plan.steps:
        if any(dep not in seen for dep in step.depends_on):
            errors.append(f"dependency-order:{step.step_id}")
        seen.add(step.step_id)
    return tuple(errors)


__all__ = ["ValidationReleaseExecutionPlan", "ValidationReleasePlanStep", "build_validation_release_execution_plan", "validate_validation_release_execution_plan"]
