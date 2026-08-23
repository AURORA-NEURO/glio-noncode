"""Dependency-safe workflow planning for coordination operations."""

from __future__ import annotations

from typing import Any

from .coordination_architecture_contracts import (
    CoordinationFixture,
    CoordinationOperationSpec,
    CoordinationPlan,
    CoordinationPlanNode,
    addressed,
)


def _node(spec: CoordinationOperationSpec, ordinal: int) -> CoordinationPlanNode:
    body = {
        "operation_id": spec.operation_id,
        "ordinal": ordinal,
        "dependencies": spec.dependencies,
        "budget_units": spec.budget_units,
    }
    return CoordinationPlanNode(**body, content_address=addressed(body, "coordination-plan-node"))


def compile_coordination_plan(
    fixture: CoordinationFixture,
    *,
    capacity_units: int | None = None,
) -> CoordinationPlan:
    """Compile operation dependencies with deterministic cycle and budget checks."""

    specs = {item.operation_id: item for item in fixture.operations}
    remaining = {item.operation_id: set(item.dependencies) for item in fixture.operations}
    issues: list[str] = []
    order: list[str] = []
    while remaining:
        ready = sorted(operation_id for operation_id, dependencies in remaining.items() if not dependencies)
        if not ready:
            issues.append("dependency_cycle")
            break
        order.extend(ready)
        for operation_id in ready:
            remaining.pop(operation_id)
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    for spec in fixture.operations:
        for dependency in spec.dependencies:
            if dependency not in specs:
                issues.append(f"missing_dependency:{spec.operation_id}:{dependency}")
    nodes = tuple(_node(specs[operation_id], ordinal) for ordinal, operation_id in enumerate(order, start=1))
    total_budget = sum(node.budget_units for node in nodes)
    if capacity_units is not None and total_budget > capacity_units:
        issues.append("plan_budget_exceeded")
    body: dict[str, Any] = {
        "plan_id": f"{fixture.fixture_id}:plan",
        "nodes": nodes,
        "total_budget_units": total_budget,
        "accepted": not issues and len(nodes) == len(fixture.operations),
        "issues": tuple(sorted(set(issues))),
    }
    return CoordinationPlan(**body, content_address=addressed(body, "coordination-plan"))


def audit_coordination_plan(plan: CoordinationPlan, expected_count: int = 16) -> tuple[str, ...]:
    """Return stable issues for a compiled plan without executing work."""

    issues: list[str] = []
    if not plan.accepted:
        issues.extend(plan.issues)
    if len(plan.nodes) != expected_count:
        issues.append("node_count_mismatch")
    if tuple(node.ordinal for node in plan.nodes) != tuple(range(1, len(plan.nodes) + 1)):
        issues.append("ordinal_gap")
    if len({node.operation_id for node in plan.nodes}) != len(plan.nodes):
        issues.append("duplicate_operation")
    return tuple(sorted(set(issues)))


__all__ = ["compile_coordination_plan", "audit_coordination_plan"]
