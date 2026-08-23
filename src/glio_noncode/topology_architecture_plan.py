"""Dependency plan for the ordered D09 topology operations."""

from __future__ import annotations

from .topology_architecture_contracts import (
    TopologyArchitectureFixture,
    TopologyArchitecturePlan,
    TopologyArchitecturePlanNode,
    addressed,
)


def build_topology_architecture_plan(
    fixture: TopologyArchitectureFixture,
) -> TopologyArchitecturePlan:
    known = {item.operation_id for item in fixture.operations}
    nodes: list[TopologyArchitecturePlanNode] = []
    for operation in fixture.operations:
        ready = not (set(operation.dependencies) - known) and all(
            dependency in {node.operation_id for node in nodes}
            for dependency in operation.dependencies
        )
        dependency_text = ", ".join(operation.dependencies) or "fixture validation"
        detail = (
            f"{operation.operation_id} is ready after {dependency_text}"
            if ready
            else f"{operation.operation_id} is held for an unresolved dependency"
        )
        body = {
            "operation_id": operation.operation_id,
            "ordinal": operation.ordinal,
            "dependencies": operation.dependencies,
            "family": operation.family,
            "plane": operation.plane,
            "ready": ready,
            "detail": detail,
        }
        nodes.append(
            TopologyArchitecturePlanNode(
                **body, content_address=addressed(body, "topology-plan-node")
            )
        )
    accepted = len(nodes) == 16 and all(node.ready for node in nodes)
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "accepted": accepted}
    return TopologyArchitecturePlan(
        fixture.fixture_id, tuple(nodes), accepted, addressed(body, "topology-plan")
    )


def topology_architecture_operation_order(plan: TopologyArchitecturePlan) -> tuple[str, ...]:
    return tuple(node.operation_id for node in sorted(plan.nodes, key=lambda item: item.ordinal))


__all__ = ["build_topology_architecture_plan", "topology_architecture_operation_order"]
