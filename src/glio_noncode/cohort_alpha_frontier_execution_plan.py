"""Ordered execution plan for local, CI, and release verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_runbook import CohortAlphaFrontierRunbook
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierExecutionAction:
    order: int
    action_id: str
    environment: str
    command: str
    artifact: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierExecutionPlan:
    actions: tuple[CohortAlphaFrontierExecutionAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_execution_plan(runbook: CohortAlphaFrontierRunbook) -> CohortAlphaFrontierExecutionPlan:
    actions = tuple(CohortAlphaFrontierExecutionAction(index, f"action-{step.step_id}", "local" if index < 4 else "ci", step.command, f"output/{step.step_id}.json", step.stop_on_failure, content_hash({"order": index, "id": step.step_id, "environment": "local" if index < 4 else "ci", "command": step.command, "artifact": f"output/{step.step_id}.json", "required": step.stop_on_failure}, prefix="alpha-execution")) for index, step in enumerate(runbook.steps, 1))
    return CohortAlphaFrontierExecutionPlan(actions, runbook.accepted and len(actions) == len(runbook.steps) and tuple(item.order for item in actions) == tuple(range(1, len(actions) + 1)), content_hash(actions, prefix="alpha-execution-plan"))


__all__ = ["CohortAlphaFrontierExecutionAction", "CohortAlphaFrontierExecutionPlan", "build_cohort_alpha_frontier_execution_plan"]
