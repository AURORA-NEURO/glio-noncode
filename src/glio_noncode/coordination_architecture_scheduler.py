"""Deterministic budget and dependency scheduler."""

from __future__ import annotations

from .coordination_architecture_contracts import CoordinationPlan, CoordinationSchedule, addressed


DEFAULT_COORDINATION_CAPACITY = 192


def schedule_coordination_plan(plan: CoordinationPlan, *, capacity_units: int = DEFAULT_COORDINATION_CAPACITY) -> CoordinationSchedule:
    issues = list(plan.issues)
    if plan.total_budget_units > capacity_units:
        issues.append("capacity_exceeded")
    if not plan.nodes:
        issues.append("empty_plan")
    order = tuple(node.operation_id for node in plan.nodes)
    body = {
        "schedule_id": f"{plan.plan_id}:schedule",
        "order": order,
        "capacity_units": capacity_units,
        "used_units": plan.total_budget_units,
        "accepted": not issues and plan.accepted,
        "issues": tuple(sorted(set(issues))),
    }
    return CoordinationSchedule(**body, content_address=addressed(body, "coordination-schedule"))


__all__ = ["DEFAULT_COORDINATION_CAPACITY", "schedule_coordination_plan"]
