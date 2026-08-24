"""Dependency-safe D13 operation planning."""

from __future__ import annotations

from .planning_architecture_contracts import (
    PlanningArchitectureFixture,
    PlanningArchitecturePlan,
    PlanningArchitecturePlanNode,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture


def build_planning_architecture_plan(
    fixture: PlanningArchitectureFixture | None = None,
) -> PlanningArchitecturePlan:
    selected = fixture or default_planning_architecture_fixture()
    operation_ids = {item.operation_id for item in selected.operations}
    nodes: list[PlanningArchitecturePlanNode] = []
    for operation in selected.operations:
        dependencies_resolve = all(
            dependency in operation_ids and dependency < operation.operation_id
            for dependency in operation.dependencies
        )
        body = {
            "operation_id": operation.operation_id,
            "ordinal": operation.ordinal,
            "dependencies": operation.dependencies,
            "family": operation.family,
            "plane": operation.plane,
            "ready": dependencies_resolve,
            "detail": (
                "dependencies resolve to earlier operation IDs"
                if dependencies_resolve
                else "dependency resolution requires review"
            ),
        }
        nodes.append(
            PlanningArchitecturePlanNode(
                **body,
                content_address=addressed(body, "planning-plan-node"),
            )
        )
    body = {"fixture_id": selected.fixture_id, "nodes": nodes}
    return PlanningArchitecturePlan(
        selected.fixture_id,
        tuple(nodes),
        all(item.ready for item in nodes),
        addressed(body, "planning-plan"),
    )


def planning_architecture_dependency_map(
    fixture: PlanningArchitectureFixture | None = None,
) -> dict[str, tuple[str, ...]]:
    selected = fixture or default_planning_architecture_fixture()
    return {item.operation_id: item.dependencies for item in selected.operations}


def planning_architecture_plan_summary(plan: PlanningArchitecturePlan) -> dict[str, object]:
    return {
        "fixture_id": plan.fixture_id,
        "accepted": plan.accepted,
        "node_count": len(plan.nodes),
        "ready_count": sum(item.ready for item in plan.nodes),
        "blocked_nodes": [item.operation_id for item in plan.nodes if not item.ready],
        "dependency_edge_count": sum(len(item.dependencies) for item in plan.nodes),
    }


__all__ = [
    "build_planning_architecture_plan",
    "planning_architecture_dependency_map",
    "planning_architecture_plan_summary",
]
