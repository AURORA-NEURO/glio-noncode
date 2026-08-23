"""Dependency graph and execution readiness for the sixteen D08 operations."""

from __future__ import annotations

from .cell_state_architecture_contracts import (
    CellStateArchitectureFixture,
    CellStateArchitecturePlan,
    CellStateArchitecturePlanNode,
    addressed,
)


def build_cell_state_architecture_plan(
    fixture: CellStateArchitectureFixture,
) -> CellStateArchitecturePlan:
    """Build a linear, inspectable plan while verifying every dependency."""
    known = {item.operation_id for item in fixture.operations}
    nodes: list[CellStateArchitecturePlanNode] = []
    for operation in fixture.operations:
        dependencies = tuple(operation.dependencies)
        ready = not (set(dependencies) - known) and all(
            dependency in {node.operation_id for node in nodes} for dependency in dependencies
        )
        detail = (
            f"{operation.operation_id} {operation.operation.value} is ready after "
            f"{', '.join(dependencies) if dependencies else 'fixture validation'}"
            if ready
            else f"{operation.operation_id} is held because a dependency is unresolved"
        )
        body = {
            "operation_id": operation.operation_id,
            "ordinal": operation.ordinal,
            "dependencies": dependencies,
            "family": operation.family,
            "plane": operation.plane,
            "ready": ready,
            "detail": detail,
        }
        nodes.append(
            CellStateArchitecturePlanNode(
                **body, content_address=addressed(body, "cell-state-plan-node")
            )
        )
    accepted = len(nodes) == 16 and all(node.ready for node in nodes)
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "accepted": accepted}
    return CellStateArchitecturePlan(
        fixture.fixture_id, tuple(nodes), accepted, addressed(body, "cell-state-plan")
    )


def plan_operation_order(plan: CellStateArchitecturePlan) -> tuple[str, ...]:
    """Return the stable order used by replay and stage construction."""
    return tuple(node.operation_id for node in sorted(plan.nodes, key=lambda item: item.ordinal))


def plan_summary(plan: CellStateArchitecturePlan) -> dict[str, object]:
    return {
        "fixture_id": plan.fixture_id,
        "accepted": plan.accepted,
        "node_count": len(plan.nodes),
        "ready_count": sum(node.ready for node in plan.nodes),
        "operation_order": list(plan_operation_order(plan)),
        "content_address": plan.content_address,
    }


__all__ = ["build_cell_state_architecture_plan", "plan_operation_order", "plan_summary"]
